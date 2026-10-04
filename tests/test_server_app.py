"""Tests de server_app (servidor TCP real en localhost, puerto efímero)."""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from typing import Any

import pytest

from spo_core import db
from spo_core.patterns.singleton import SingletonMeta
from spo_core.protocol import receive_message, send_message
from spo_core.server_app import SingletonProxyObserverServer
from spo_core.service import CorporateService


class FakeTable:
    """Simula una tabla de DynamoDB en memoria, sin llamar a AWS."""

    def __init__(self) -> None:
        """Arranca con el almacen vacio."""
        self.items: dict[str, dict[str, Any]] = {}

    def get_item(self, Key: dict[str, Any]) -> dict[str, Any]:  # noqa: N803
        """Simula dynamodb.Table.get_item."""
        item = self.items.get(Key["id"])
        return {"Item": item} if item is not None else {}

    def put_item(self, Item: dict[str, Any]) -> dict[str, Any]:  # noqa: N803
        """Simula dynamodb.Table.put_item."""
        self.items[Item["id"]] = Item
        return {}

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        """Simula dynamodb.Table.scan (sin paginacion, alcanza para los tests)."""
        return {"Items": list(self.items.values())}


class FakeResource:
    """Simula boto3.resource("dynamodb"), devolviendo siempre la misma FakeTable."""

    def __init__(self) -> None:
        """Crea una tabla falsa por nombre, para poder inspeccionarla en el test."""
        self.tables: dict[str, FakeTable] = {}

    def Table(self, name: str) -> FakeTable:  # noqa: N802
        """Simula dynamodb.resource.Table(name)."""
        return self.tables.setdefault(name, FakeTable())


@pytest.fixture
def fake_service(monkeypatch: pytest.MonkeyPatch) -> Iterator[CorporateService]:
    """CorporateService con DynamoDB mockeado en memoria."""
    resource = FakeResource()
    monkeypatch.setattr(db.boto3, "resource", lambda service_name: resource)
    SingletonMeta.reset_instances()
    yield CorporateService()
    SingletonMeta.reset_instances()


@pytest.fixture
def running_server(fake_service: CorporateService) -> Iterator[SingletonProxyObserverServer]:
    """Levanta el servidor real en un puerto efimero (0 = elegido por el SO)."""
    server = SingletonProxyObserverServer(0, fake_service, verbose=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_server_accepts_real_tcp_connection(running_server: SingletonProxyObserverServer) -> None:
    """El servidor acepta una conexion TCP real y responde correctamente a un get."""
    port = running_server.server_address[1]
    client = socket.create_connection(("localhost", port), timeout=2)
    try:
        send_message(client, {"UUID": "cpu-1", "ACTION": "get", "ID": "no-existe"})
        response = receive_message(client)
        assert response["ACTION"] == "get"
        assert "ERROR" in response
    finally:
        client.close()


def test_server_handles_multiple_concurrent_clients(
    running_server: SingletonProxyObserverServer,
) -> None:
    """El servidor atiende varias conexiones simultaneas sin bloquearse entre si."""
    port = running_server.server_address[1]
    clients = [socket.create_connection(("localhost", port), timeout=2) for _ in range(5)]
    try:
        for i, client in enumerate(clients):
            send_message(client, {"UUID": f"cpu-{i}", "ACTION": "set", "ID": f"id-{i}", "sede": "A"})
        for client in clients:
            response = receive_message(client)
            assert response["ACTION"] == "set"
    finally:
        for client in clients:
            client.close()


def test_starting_server_twice_on_same_port_fails(fake_service: CorporateService) -> None:
    """Levantar un segundo servidor en el mismo puerto falla (requisito de la consigna)."""
    first = SingletonProxyObserverServer(0, fake_service, verbose=False)
    port = first.server_address[1]
    try:
        with pytest.raises(OSError):
            SingletonProxyObserverServer(port, fake_service, verbose=False)
    finally:
        first.server_close()


def test_main_returns_error_when_port_is_taken(
    fake_service: CorporateService, capsys: pytest.CaptureFixture[str]
) -> None:
    """main() devuelve codigo de error si el puerto ya esta en uso (doble arranque)."""
    from spo_core.server_app import main

    blocker = SingletonProxyObserverServer(0, fake_service, verbose=False)
    port = blocker.server_address[1]
    try:
        exit_code = main([f"-p={port}"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "No se pudo iniciar el servidor" in captured.err
    finally:
        blocker.server_close()

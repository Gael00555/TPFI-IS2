"""Suite de aceptación: mapea cada punto exigido por la sección "Validación y
Verificación" de la consigna a un escenario de prueba de punta a punta
(servidor TCP real en un puerto efímero + clientes reales), para facilitar
la trazabilidad entre el enunciado y los tests. La lógica de bajo nivel de
cada componente ya está cubierta en los test_*.py especificos (singleton,
proxy, observer, db, service, protocol, cli_args, client_core, observer_core,
server_core, server_app); esta suite verifica el comportamiento integrado.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from typing import Any

import pytest

from spo_core import db
from spo_core.cli_args import (
    parse_observerclient_args,
    parse_server_args,
    parse_singletonclient_args,
)
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
def fake_resource(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeResource]:
    """Reemplaza boto3.resource por una version en memoria durante el test."""
    resource = FakeResource()
    monkeypatch.setattr(db.boto3, "resource", lambda service_name: resource)
    SingletonMeta.reset_instances()
    yield resource
    SingletonMeta.reset_instances()


@pytest.fixture
def running_server(fake_resource: FakeResource) -> Iterator[tuple[SingletonProxyObserverServer, int]]:
    """Levanta el servidor real en un puerto efimero, con DynamoDB mockeado."""
    server = SingletonProxyObserverServer(0, CorporateService(), verbose=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, server.server_address[1]
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def _connect(port: int) -> socket.socket:
    """Abre una conexion TCP real al servidor de prueba."""
    return socket.create_connection(("localhost", port), timeout=5)


# --- 1. Camino feliz de cada accion, con auditoria en CorporateLog ---------


def test_acceptance_happy_path_set_get_list_subscribe(
    running_server: tuple[SingletonProxyObserverServer, int],
    fake_resource: FakeResource,
) -> None:
    """Camino feliz de las 4 acciones (set/get/list/subscribe), con auditoria."""
    _, port = running_server

    observer = _connect(port)
    send_message(observer, {"UUID": "cpu-obs", "ACTION": "subscribe"})
    assert receive_message(observer)["STATUS"] == "OK"

    actor = _connect(port)
    send_message(actor, {"UUID": "cpu-actor", "ACTION": "set", "ID": "ACC-01", "sede": "FCyT"})
    set_response = receive_message(actor)
    assert set_response["ACTION"] == "set"

    notification = receive_message(observer)
    assert notification["ACTION"] == "change"
    assert notification["ID"] == "ACC-01"

    send_message(actor, {"UUID": "cpu-actor", "ACTION": "get", "ID": "ACC-01"})
    get_response = receive_message(actor)
    assert get_response["DATA"]["sede"] == "FCyT"

    send_message(actor, {"UUID": "cpu-actor", "ACTION": "list"})
    list_response = receive_message(actor)
    assert any(item["id"] == "ACC-01" for item in list_response["DATA"])

    log_actions = {entry["action"] for entry in fake_resource.tables[db.CORPORATE_LOG_TABLE_NAME].items.values()}
    assert log_actions == {"subscribe", "set", "get", "list"}

    observer.close()
    actor.close()


# --- 2. Argumentos malformados en cada uno de los 3 programas ---------------


def test_acceptance_malformed_arguments_singletonclient() -> None:
    """singletonclient.py sin -i (obligatorio) es un argumento malformado."""
    with pytest.raises(SystemExit):
        parse_singletonclient_args([])


def test_acceptance_malformed_arguments_observerclient() -> None:
    """observerclient.py con -p no numerico es un argumento malformado."""
    with pytest.raises(SystemExit):
        parse_observerclient_args(["-p=no-es-un-puerto"])


def test_acceptance_malformed_arguments_server() -> None:
    """singletonproxyobserver.py con -p no numerico es un argumento malformado."""
    with pytest.raises(SystemExit):
        parse_server_args(["-p=no-es-un-puerto"])


# --- 3. Requerimiento sin datos minimos necesarios --------------------------


def test_acceptance_request_missing_minimum_data(
    running_server: tuple[SingletonProxyObserverServer, int],
) -> None:
    """Un get sin ID (dato minimo necesario) responde error sin tirar el servidor."""
    _, port = running_server
    sock = _connect(port)

    send_message(sock, {"UUID": "cpu-1", "ACTION": "get"})
    response = receive_message(sock)

    assert "ERROR" in response
    sock.close()


# --- 4. Manejo en clientes de server aplicativo caido -----------------------


def test_acceptance_client_handles_server_down() -> None:
    """singletonclient.py maneja de forma controlada un servidor caido."""
    from spo_core.client_core import run_singleton_client

    def refused_connector(host: str, port: int) -> socket.socket:
        raise ConnectionRefusedError("servidor caido (simulado)")

    import json
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / "input.json"
        input_path.write_text(json.dumps({"UUID": "cpu-1", "ACTION": "get", "ID": "x"}))

        exit_code = run_singleton_client(str(input_path), None, connector=refused_connector)

    assert exit_code != 0


# --- 5. Intento de levantar dos veces el servidor de aplicaciones -----------


def test_acceptance_cannot_start_server_twice_on_same_port(fake_resource: FakeResource) -> None:
    """Un segundo servidor en el mismo puerto falla, sin afectar al primero."""
    first = SingletonProxyObserverServer(0, CorporateService(), verbose=False)
    port = first.server_address[1]
    thread = threading.Thread(target=first.serve_forever, daemon=True)
    thread.start()

    try:
        with pytest.raises(OSError):
            SingletonProxyObserverServer(port, CorporateService(), verbose=False)

        # El primer servidor sigue operativo pese al intento fallido del segundo.
        sock = _connect(port)
        send_message(sock, {"UUID": "cpu-1", "ACTION": "list"})
        response = receive_message(sock)
        assert response["ACTION"] == "list"
        sock.close()
    finally:
        first.shutdown()
        first.server_close()
        thread.join(timeout=2)

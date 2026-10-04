"""Tests de server_core (atención de conexiones del servidor)."""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from typing import Any

import pytest

from spo_core import db
from spo_core.patterns.singleton import SingletonMeta
from spo_core.protocol import receive_message, send_message
from spo_core.server_core import handle_connection
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
def service(monkeypatch: pytest.MonkeyPatch) -> Iterator[CorporateService]:
    """CorporateService con DynamoDB mockeado en memoria."""
    resource = FakeResource()
    monkeypatch.setattr(db.boto3, "resource", lambda service_name: resource)
    SingletonMeta.reset_instances()
    yield CorporateService()
    SingletonMeta.reset_instances()


class ConnectedServer:
    """Levanta handle_connection en un hilo, conectado a un socket de prueba."""

    def __init__(self, service: CorporateService) -> None:
        """Crea el par de sockets y arranca el hilo del servidor."""
        self.client_sock, self._server_sock = socket.socketpair()
        self._thread = threading.Thread(
            target=handle_connection,
            args=(self._server_sock, service),
            kwargs={"verbose": False},
            daemon=True,
        )
        self._thread.start()

    def send(self, payload: dict[str, Any]) -> None:
        """Envia un mensaje al servidor, como si fuera el cliente."""
        send_message(self.client_sock, payload)

    def receive(self) -> dict[str, Any]:
        """Recibe la proxima respuesta del servidor."""
        return receive_message(self.client_sock)

    def close(self) -> None:
        """Cierra la conexion y espera a que el hilo del servidor termine."""
        self.client_sock.close()
        self._thread.join(timeout=2)


@pytest.fixture
def connected_server(service: CorporateService) -> Iterator[ConnectedServer]:
    """Servidor de prueba ya conectado, listo para enviar/recibir mensajes."""
    server = ConnectedServer(service)
    yield server
    server.close()


def test_get_action_returns_not_found(connected_server: ConnectedServer) -> None:
    """Un get sobre un id inexistente responde con error, sin tirar el servidor."""
    connected_server.send({"UUID": "cpu-1", "ACTION": "get", "ID": "no-existe"})

    response = connected_server.receive()

    assert response["ACTION"] == "get"
    assert "ERROR" in response


def test_set_then_get_roundtrip(connected_server: ConnectedServer) -> None:
    """Un set seguido de un get devuelve los datos recien grabados."""
    connected_server.send({"UUID": "cpu-1", "ACTION": "set", "ID": "UADER-TEST-01", "sede": "FCyT"})
    set_response = connected_server.receive()

    connected_server.send({"UUID": "cpu-1", "ACTION": "get", "ID": "UADER-TEST-01"})
    get_response = connected_server.receive()

    assert set_response["ACTION"] == "set"
    assert set_response["DATA"]["sede"] == "FCyT"
    assert get_response["DATA"]["sede"] == "FCyT"


def test_set_without_fields_returns_error(connected_server: ConnectedServer) -> None:
    """Un set sin ningun campo a modificar responde error (UpdateAccessError)."""
    connected_server.send({"UUID": "cpu-1", "ACTION": "set", "ID": "UADER-TEST-02"})

    response = connected_server.receive()

    assert "ERROR" in response


def test_list_returns_all_records(connected_server: ConnectedServer) -> None:
    """list devuelve todos los registros cargados hasta el momento."""
    connected_server.send({"UUID": "cpu-1", "ACTION": "set", "ID": "id-1", "sede": "A"})
    connected_server.receive()
    connected_server.send({"UUID": "cpu-1", "ACTION": "set", "ID": "id-2", "sede": "B"})
    connected_server.receive()

    connected_server.send({"UUID": "cpu-1", "ACTION": "list"})
    response = connected_server.receive()

    ids = {item["id"] for item in response["DATA"]}
    assert {"id-1", "id-2"}.issubset(ids)


def test_subscribe_responds_ok(connected_server: ConnectedServer) -> None:
    """Un subscribe exitoso responde STATUS OK."""
    connected_server.send({"UUID": "cpu-obs", "ACTION": "subscribe"})

    response = connected_server.receive()

    assert response["ACTION"] == "subscribe"
    assert response["STATUS"] == "OK"


def test_missing_uuid_returns_error(connected_server: ConnectedServer) -> None:
    """Un mensaje sin UUID responde error, sin requerir datos minimos de mas."""
    connected_server.send({"ACTION": "get", "ID": "algo"})

    response = connected_server.receive()

    assert "ERROR" in response


def test_invalid_action_returns_error(connected_server: ConnectedServer) -> None:
    """Una ACTION desconocida responde error."""
    connected_server.send({"UUID": "cpu-1", "ACTION": "borrar_todo"})

    response = connected_server.receive()

    assert "ERROR" in response


def test_get_without_id_returns_error(connected_server: ConnectedServer) -> None:
    """Un get sin ID responde error (dato minimo faltante)."""
    connected_server.send({"UUID": "cpu-1", "ACTION": "get"})

    response = connected_server.receive()

    assert "ERROR" in response


def test_malformed_json_returns_error_and_keeps_connection_alive(
    connected_server: ConnectedServer,
) -> None:
    """Una linea que no es JSON valido no tira la conexion: responde error y sigue."""
    connected_server.client_sock.sendall(b"esto no es json\n")
    error_response = connected_server.receive()

    connected_server.send({"UUID": "cpu-1", "ACTION": "get", "ID": "no-existe"})
    next_response = connected_server.receive()

    assert "ERROR" in error_response
    assert next_response["ACTION"] == "get"


def test_set_notifies_subscribed_client(service: CorporateService) -> None:
    """Un set realizado por un cliente notifica a otro cliente ya suscripto."""
    subscriber = ConnectedServer(service)
    subscriber.send({"UUID": "cpu-obs", "ACTION": "subscribe"})
    subscriber.receive()  # confirmacion del subscribe

    actor = ConnectedServer(service)
    actor.send({"UUID": "cpu-actor", "ACTION": "set", "ID": "UADER-TEST-03", "sede": "FCyT"})
    actor.receive()  # respuesta directa al actor

    notification = subscriber.receive()

    assert notification["ACTION"] == "change"
    assert notification["ID"] == "UADER-TEST-03"

    subscriber.close()
    actor.close()

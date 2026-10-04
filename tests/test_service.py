"""Tests de CorporateService (integracion de Singleton + Proxy + Observer)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from spo_core import db
from spo_core.patterns.singleton import SingletonMeta
from spo_core.service import CorporateService, RecordNotFoundError


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


class FakeSubscriber:
    """Suscriptor de prueba que registra lo que recibe."""

    def __init__(self) -> None:
        """Arranca sin notificaciones recibidas."""
        self.received: list[dict[str, Any]] = []

    def send_update(self, data: dict[str, Any]) -> bool:
        """Guarda la notificacion recibida."""
        self.received.append(data)
        return True


@pytest.fixture
def fake_resource(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeResource]:
    """Reemplaza boto3.resource por una version en memoria durante el test."""
    resource = FakeResource()
    monkeypatch.setattr(db.boto3, "resource", lambda service_name: resource)
    SingletonMeta.reset_instances()
    yield resource
    SingletonMeta.reset_instances()


def test_get_raises_when_missing(fake_resource: FakeResource) -> None:
    """get() lanza RecordNotFoundError si el id no existe."""
    service = CorporateService()

    with pytest.raises(RecordNotFoundError):
        service.get("no-existe", client_uuid="cpu-1", session_id="s-1")


def test_get_audits_the_access(fake_resource: FakeResource) -> None:
    """Cada get() deja un registro de auditoria en CorporateLog."""
    service = CorporateService()
    service.set("UADER-FCYT-IS2", {"sede": "FCyT"}, client_uuid="cpu-1", session_id="s-1")

    service.get("UADER-FCYT-IS2", client_uuid="cpu-2", session_id="s-2")

    log_items = list(fake_resource.tables[db.CORPORATE_LOG_TABLE_NAME].items.values())
    get_entries = [e for e in log_items if e["action"] == "get"]
    assert len(get_entries) == 1
    assert get_entries[0]["UUID"] == "cpu-2"
    assert get_entries[0]["recordId"] == "UADER-FCYT-IS2"


def test_set_creates_record_and_audits(fake_resource: FakeResource) -> None:
    """set() crea el registro y deja auditoria de la accion."""
    service = CorporateService()

    result = service.set("UADER-FCYT-IS2", {"sede": "FCyT"}, client_uuid="cpu-1", session_id="s-1")

    assert result["sede"] == "FCyT"
    log_items = list(fake_resource.tables[db.CORPORATE_LOG_TABLE_NAME].items.values())
    set_entries = [e for e in log_items if e["action"] == "set"]
    assert len(set_entries) == 1
    assert set_entries[0]["recordId"] == "UADER-FCYT-IS2"


def test_set_notifies_subscribers(fake_resource: FakeResource) -> None:
    """Tras un set exitoso, todos los suscriptos reciben la notificacion."""
    service = CorporateService()
    subscriber = FakeSubscriber()
    service.subscribe(subscriber, client_uuid="cpu-obs", session_id="s-obs")

    service.set("UADER-FCYT-IS2", {"sede": "FCyT"}, client_uuid="cpu-1", session_id="s-1")

    assert len(subscriber.received) == 1
    assert subscriber.received[0]["ACTION"] == "change"
    assert subscriber.received[0]["ID"] == "UADER-FCYT-IS2"


def test_list_all_audits_the_access(fake_resource: FakeResource) -> None:
    """list_all() devuelve los registros y deja auditoria."""
    service = CorporateService()
    service.set("id-1", {"sede": "A"}, client_uuid="cpu-1", session_id="s-1")
    service.set("id-2", {"sede": "B"}, client_uuid="cpu-1", session_id="s-1")

    records = service.list_all(client_uuid="cpu-2", session_id="s-2")

    assert {r["id"] for r in records} == {"id-1", "id-2"}
    log_items = list(fake_resource.tables[db.CORPORATE_LOG_TABLE_NAME].items.values())
    assert any(e["action"] == "list" for e in log_items)


def test_subscribe_audits_and_registers(fake_resource: FakeResource) -> None:
    """subscribe() registra al suscriptor y deja auditoria de la accion."""
    service = CorporateService()
    subscriber = FakeSubscriber()

    service.subscribe(subscriber, client_uuid="cpu-obs", session_id="s-obs")

    assert service.subscriber_count == 1
    log_items = list(fake_resource.tables[db.CORPORATE_LOG_TABLE_NAME].items.values())
    assert any(e["action"] == "subscribe" for e in log_items)


def test_unsubscribe_removes_subscriber(fake_resource: FakeResource) -> None:
    """unsubscribe() remueve al suscriptor sin generar auditoria adicional."""
    service = CorporateService()
    subscriber = FakeSubscriber()
    service.subscribe(subscriber, client_uuid="cpu-obs", session_id="s-obs")

    service.unsubscribe(subscriber)

    assert service.subscriber_count == 0

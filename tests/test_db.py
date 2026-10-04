"""Tests de acceso a DynamoDB (CorporateDataSingleton y CorporateLogSingleton)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from spo_core import db
from spo_core.patterns.singleton import SingletonMeta


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


def test_get_record_returns_none_when_missing(fake_resource: FakeResource) -> None:
    """get_record devuelve None si el id no existe en la tabla."""
    data = db.CorporateDataSingleton()

    assert data.get_record("no-existe") is None


def test_apply_update_creates_new_record_with_blank_fields(fake_resource: FakeResource) -> None:
    """Un set sobre un id nuevo crea el registro con los campos faltantes en blanco."""
    data = db.CorporateDataSingleton()

    result = data.apply_update("UADER-FCYT-IS2", {"telefono": "03442 43-1442"})

    assert result["id"] == "UADER-FCYT-IS2"
    assert result["telefono"] == "03442 43-1442"
    assert result["CUIT"] == ""
    assert result["localidad"] == ""


def test_apply_update_merges_existing_record(fake_resource: FakeResource) -> None:
    """Un set sobre un id existente conserva los campos no informados."""
    data = db.CorporateDataSingleton()
    data.apply_update("UADER-FCYT-IS2", {"CUIT": "30-70925411-8", "sede": "FCyT"})

    result = data.apply_update("UADER-FCYT-IS2", {"sede": "FCyT-Nueva"})

    assert result["CUIT"] == "30-70925411-8"
    assert result["sede"] == "FCyT-Nueva"


def test_list_records_returns_all_items(fake_resource: FakeResource) -> None:
    """list_records devuelve todos los registros cargados en la tabla."""
    data = db.CorporateDataSingleton()
    data.apply_update("id-1", {"sede": "FCyT"})
    data.apply_update("id-2", {"sede": "Otra"})

    records = data.list_records()

    assert {r["id"] for r in records} == {"id-1", "id-2"}


def test_corporate_data_is_singleton(fake_resource: FakeResource) -> None:
    """CorporateDataSingleton siempre devuelve la misma instancia."""
    assert db.CorporateDataSingleton() is db.CorporateDataSingleton()


def test_corporate_log_is_singleton_and_independent(fake_resource: FakeResource) -> None:
    """CorporateLogSingleton es un singleton independiente de CorporateDataSingleton."""
    log_a = db.CorporateLogSingleton()
    log_b = db.CorporateLogSingleton()
    data = db.CorporateDataSingleton()

    assert log_a is log_b
    assert log_a is not data


def test_append_entry_stores_action_with_timestamp(fake_resource: FakeResource) -> None:
    """append_entry graba UUID, sesion, accion y timestamp en CorporateLog."""
    log = db.CorporateLogSingleton()

    entry = log.append_entry(
        client_uuid="cpu-123",
        session_id="session-abc",
        action="get",
        record_id="UADER-FCYT-IS2",
    )

    stored = fake_resource.tables[db.CORPORATE_LOG_TABLE_NAME].items[entry["id"]]
    assert stored["UUID"] == "cpu-123"
    assert stored["session"] == "session-abc"
    assert stored["action"] == "get"
    assert stored["recordId"] == "UADER-FCYT-IS2"
    assert "timestamp" in stored

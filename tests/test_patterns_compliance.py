"""Verifica que las clases implementan efectivamente los patrones exigidos."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from spo_core import db
from spo_core.patterns.observer import EventPublisher
from spo_core.patterns.proxy import UpdateProxy
from spo_core.patterns.singleton import SingletonMeta
from spo_core.service import CorporateService


class FakeTable:
    """Tabla en memoria, sin llamar a AWS."""

    def __init__(self) -> None:
        """Arranca vacia."""
        self.items: dict[str, dict[str, object]] = {}

    def get_item(self, Key: dict[str, str]) -> dict[str, object]:  # noqa: N803
        """Simula get_item."""
        item = self.items.get(Key["id"])
        return {"Item": item} if item is not None else {}

    def put_item(self, Item: dict[str, object]) -> dict[str, object]:  # noqa: N803
        """Simula put_item."""
        self.items[str(Item["id"])] = Item
        return {}

    def scan(self, **kwargs: object) -> dict[str, object]:
        """Simula scan."""
        return {"Items": list(self.items.values())}


class FakeResource:
    """Simula boto3.resource('dynamodb')."""

    def __init__(self) -> None:
        """Arranca sin tablas."""
        self.tables: dict[str, FakeTable] = {}

    def Table(self, name: str) -> FakeTable:  # noqa: N802
        """Simula resource.Table."""
        return self.tables.setdefault(name, FakeTable())


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> Iterator[CorporateService]:
    """CorporateService con DynamoDB mockeado."""
    resource = FakeResource()
    monkeypatch.setattr(db.boto3, "resource", lambda service_name: resource)
    SingletonMeta.reset_instances()
    yield CorporateService()
    SingletonMeta.reset_instances()


def test_table_access_classes_use_singleton_metaclass() -> None:
    """El acceso a cada tabla es un Singleton (metaclase SingletonMeta)."""
    assert isinstance(db.CorporateDataSingleton, SingletonMeta)
    assert isinstance(db.CorporateLogSingleton, SingletonMeta)


def test_each_table_has_its_own_singleton_instance(service: CorporateService) -> None:
    """Hay dos singletons independientes: uno por tabla."""
    assert db.CorporateDataSingleton() is db.CorporateDataSingleton()
    assert db.CorporateLogSingleton() is db.CorporateLogSingleton()
    assert db.CorporateDataSingleton() is not db.CorporateLogSingleton()


def test_service_updates_go_through_proxy_to_data_singleton(service: CorporateService) -> None:
    """Las actualizaciones pasan por un UpdateProxy cuyo sujeto real es el Singleton de datos."""
    proxy = service._update_proxy  # noqa: SLF001
    assert isinstance(proxy, UpdateProxy)
    assert proxy._real_updater is db.CorporateDataSingleton()  # noqa: SLF001


def test_service_subscriptions_are_managed_by_observer(service: CorporateService) -> None:
    """Las subscripciones las gestiona un EventPublisher (Observer)."""
    assert isinstance(service._publisher, EventPublisher)  # noqa: SLF001

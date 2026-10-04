"""Tests del patrón Proxy."""

from __future__ import annotations

from typing import Any

import pytest

from spo_core.patterns.proxy import (
    UpdateAccessError,
    UpdateProxy,
)


class FakeRealUpdater:
    """Sujeto real de prueba: simula la escritura en la tabla."""

    def __init__(self) -> None:
        """Guarda las escrituras aplicadas para poder inspeccionarlas."""
        self.applied: list[tuple[str, dict[str, Any]]] = []

    def apply_update(self, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Simula la actualización real y devuelve el registro resultante."""
        self.applied.append((record_id, fields))
        return {"id": record_id, **fields}


def test_delegates_to_real_updater() -> None:
    """El proxy delega correctamente en el sujeto real."""
    real = FakeRealUpdater()
    proxy = UpdateProxy(real)

    result = proxy.update("UADER-FCYT-IS2", {"telefono": "03442 43-1442"})

    assert result == {"id": "UADER-FCYT-IS2", "telefono": "03442 43-1442"}
    assert real.applied == [("UADER-FCYT-IS2", {"telefono": "03442 43-1442"})]


def test_rejects_empty_record_id() -> None:
    """Sin id de registro, el proxy rechaza la actualización sin delegar."""
    real = FakeRealUpdater()
    proxy = UpdateProxy(real)

    with pytest.raises(UpdateAccessError):
        proxy.update("", {"telefono": "03442 43-1442"})

    assert real.applied == []


def test_rejects_empty_fields() -> None:
    """Sin campos para modificar, el proxy rechaza la actualización sin delegar."""
    real = FakeRealUpdater()
    proxy = UpdateProxy(real)

    with pytest.raises(UpdateAccessError):
        proxy.update("UADER-FCYT-IS2", {})

    assert real.applied == []


def test_before_and_after_hooks_are_called_in_order() -> None:
    """Los hooks de auditoría se llaman antes y después de delegar, en orden."""
    calls: list[str] = []
    real = FakeRealUpdater()
    proxy = UpdateProxy(
        real,
        on_before_update=lambda record_id, fields: calls.append(f"before:{record_id}"),
        on_after_update=lambda record_id, result: calls.append(f"after:{record_id}"),
    )

    proxy.update("UADER-FCYT-IS2", {"seqID": "24"})

    assert calls == ["before:UADER-FCYT-IS2", "after:UADER-FCYT-IS2"]


def test_works_without_hooks() -> None:
    """El proxy funciona igual si no se le pasan hooks de auditoría."""
    real = FakeRealUpdater()
    proxy = UpdateProxy(real)

    result = proxy.update("UADER-FCYT-IS2", {"seqID": "24"})

    assert result == {"id": "UADER-FCYT-IS2", "seqID": "24"}

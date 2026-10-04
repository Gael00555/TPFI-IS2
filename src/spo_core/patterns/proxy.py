"""Implementación del patrón Proxy para controlar las actualizaciones de datos."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class DataUpdater(Protocol):
    """Contrato que debe cumplir el sujeto real que aplica una actualización."""

    def apply_update(self, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Aplica la actualización sobre el registro real y devuelve el resultado."""
        ...


class UpdateAccessError(Exception):
    """Se lanza cuando el proxy rechaza una actualización antes de delegarla."""


class UpdateProxy:
    """Proxy que controla el acceso a las actualizaciones (acción "set").

    Se interpone entre quien solicita una modificación de datos y el sujeto
    real (``DataUpdater``) que efectivamente escribe en la tabla. Antes de
    delegar, valida que el pedido tenga los datos mínimos y permite registrar
    la operación mediante hooks de auditoría, sin que el sujeto real
    necesite saber nada de esa lógica.
    """

    def __init__(
        self,
        real_updater: DataUpdater,
        on_before_update: Callable[[str, dict[str, Any]], None] | None = None,
        on_after_update: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        """Guarda el sujeto real y los hooks opcionales de auditoría."""
        self._real_updater = real_updater
        self._on_before_update = on_before_update
        self._on_after_update = on_after_update

    def update(self, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Valida, delega en el sujeto real y notifica el resultado.

        Levanta ``UpdateAccessError`` si ``record_id`` está vacío o si
        ``fields`` no contiene ningún dato para modificar.
        """
        if not record_id:
            raise UpdateAccessError("El id del registro es obligatorio para actualizar.")
        if not fields:
            raise UpdateAccessError("No se recibio ningun campo para actualizar.")

        if self._on_before_update is not None:
            self._on_before_update(record_id, fields)

        result = self._real_updater.apply_update(record_id, fields)

        if self._on_after_update is not None:
            self._on_after_update(record_id, result)

        return result

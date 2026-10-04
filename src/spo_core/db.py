"""Acceso físico singleton a las tablas CorporateData y CorporateLog en DynamoDB."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

import boto3
from mypy_boto3_dynamodb.service_resource import Table

from spo_core.patterns.singleton import SingletonMeta

CORPORATE_DATA_TABLE_NAME = "CorporateData"
CORPORATE_LOG_TABLE_NAME = "CorporateLog"

# Campos del tuple CorporateData, segun la Tabla 1 del enunciado (sin contar "id",
# que es la clave primaria y se maneja aparte).
CORPORATE_DATA_FIELDS = (
    "cp",
    "CUIT",
    "domicilio",
    "idReq",
    "idSeq",
    "localidad",
    "provincia",
    "sede",
    "seqID",
    "telefono",
    "web",
)


class CorporateDataSingleton(metaclass=SingletonMeta):
    """Acceso físico único a la tabla CorporateData.

    Actua ademas como sujeto real (``DataUpdater``) del ``UpdateProxy``: expone
    ``apply_update`` con la firma que el proxy espera para delegar el "set".
    """

    def __init__(self) -> None:
        """Abre la conexion a la tabla CorporateData (una unica vez por proceso)."""
        resource = boto3.resource("dynamodb")
        self._table: Table = resource.Table(CORPORATE_DATA_TABLE_NAME)

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        """Devuelve el registro con ese id, o None si no existe."""
        response = self._table.get_item(Key={"id": record_id})
        item = response.get("Item")
        return cast(dict[str, Any] | None, item)

    def list_records(self) -> list[dict[str, Any]]:
        """Devuelve todos los registros de la tabla (pagina el scan si hace falta)."""
        items: list[dict[str, Any]] = []
        response = self._table.scan()
        items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            response = self._table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
        return items

    def apply_update(self, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Aplica un "set": fusiona si el registro existe, crea en blanco si no.

        Es el metodo que UpdateProxy invoca como sujeto real.
        """
        existing = self.get_record(record_id)
        if existing is None:
            existing = {"id": record_id, **{field: "" for field in CORPORATE_DATA_FIELDS}}

        merged = {**existing, **fields, "id": record_id}
        self._table.put_item(Item=merged)
        return merged


class CorporateLogSingleton(metaclass=SingletonMeta):
    """Acceso físico único a la tabla CorporateLog (bitacora de auditoria)."""

    def __init__(self) -> None:
        """Abre la conexion a la tabla CorporateLog (una unica vez por proceso)."""
        resource = boto3.resource("dynamodb")
        self._table: Table = resource.Table(CORPORATE_LOG_TABLE_NAME)

    def append_entry(
        self,
        *,
        client_uuid: str,
        session_id: str,
        action: str,
        record_id: str | None = None,
    ) -> dict[str, Any]:
        """Registra una accion auditable (subscribe/get/set/list) con timestamp."""
        entry: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "UUID": client_uuid,
            "session": session_id,
            "action": action,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if record_id is not None:
            entry["recordId"] = record_id

        self._table.put_item(Item=entry)
        return entry

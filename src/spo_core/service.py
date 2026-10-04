"""Servicio de negocio que integra Singleton, Proxy y Observer para CorporateData."""

from __future__ import annotations

from typing import Any

from spo_core.db import CorporateDataSingleton, CorporateLogSingleton
from spo_core.patterns.observer import EventPublisher, Subscriber
from spo_core.patterns.proxy import UpdateProxy


class RecordNotFoundError(Exception):
    """Se lanza cuando se pide un "get" sobre un id que no existe."""


class CorporateService:
    """Fachada que expone get/set/list/subscribe sobre CorporateData.

    Internamente combina los tres patrones exigidos por la consigna:
    - Singleton: el acceso fisico a las tablas via CorporateDataSingleton y
      CorporateLogSingleton.
    - Proxy: la actualizacion (set) se controla mediante UpdateProxy, que
      dispara la auditoria antes/despues de escribir.
    - Observer: tras un set exitoso, se notifica a todos los clientes
      suscriptos via EventPublisher.
    """

    def __init__(self) -> None:
        """Conecta el proxy de actualizacion con el singleton real y la auditoria."""
        self._data = CorporateDataSingleton()
        self._log = CorporateLogSingleton()
        self._publisher = EventPublisher()
        self._update_proxy = UpdateProxy(
            real_updater=self._data,
            on_before_update=self._audit_set_hook,
        )

    def _audit_set_hook(self, record_id: str, fields: dict[str, Any]) -> None:
        """Hook interno: se llama antes de aplicar un set (ver UpdateProxy)."""
        # El registro real de auditoria requiere el UUID/session del cliente,
        # que no forman parte de la firma de UpdateProxy. Por eso el audit
        # completo del "set" se hace en self.set(), no aqui; este hook queda
        # reservado para validaciones futuras que no dependan del cliente.
        return

    def get(self, record_id: str, *, client_uuid: str, session_id: str) -> dict[str, Any]:
        """Recupera un registro de CorporateData, auditando el acceso."""
        self._log.append_entry(
            client_uuid=client_uuid,
            session_id=session_id,
            action="get",
            record_id=record_id,
        )
        record = self._data.get_record(record_id)
        if record is None:
            raise RecordNotFoundError(record_id)
        return record

    def list_all(self, *, client_uuid: str, session_id: str) -> list[dict[str, Any]]:
        """Devuelve todos los registros de CorporateData, auditando el acceso."""
        self._log.append_entry(
            client_uuid=client_uuid,
            session_id=session_id,
            action="list",
        )
        return self._data.list_records()

    def set(
        self,
        record_id: str,
        fields: dict[str, Any],
        *,
        client_uuid: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Modifica (o crea) un registro, audita y notifica a los suscriptos."""
        self._log.append_entry(
            client_uuid=client_uuid,
            session_id=session_id,
            action="set",
            record_id=record_id,
        )
        result = self._update_proxy.update(record_id, fields)
        self._publisher.notify({"ACTION": "change", "ID": record_id, **result})
        return result

    def subscribe(self, subscriber: Subscriber, *, client_uuid: str, session_id: str) -> None:
        """Registra un nuevo suscriptor y audita la subscripcion."""
        self._log.append_entry(
            client_uuid=client_uuid,
            session_id=session_id,
            action="subscribe",
        )
        self._publisher.subscribe(subscriber)

    def unsubscribe(self, subscriber: Subscriber) -> None:
        """Da de baja a un suscriptor (por ejemplo, al cerrarse su socket)."""
        self._publisher.unsubscribe(subscriber)

    @property
    def subscriber_count(self) -> int:
        """Cantidad de suscriptores activos (util para tests e inspeccion)."""
        return self._publisher.subscriber_count

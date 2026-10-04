"""Lógica de atención de conexiones del servidor (sin depender de socketserver).

Esta capa recibe un socket ya aceptado y decide qué hacer con los mensajes
JSON que llegan por él, delegando toda la lógica de negocio en CorporateService.
Se mantiene separada de la clase que realmente escucha en el puerto TCP
(singletonproxyobserver.py) para poder testearla con sockets en memoria
(socket.socketpair), sin abrir puertos reales.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import uuid
from typing import Any

from spo_core.patterns.proxy import UpdateAccessError
from spo_core.protocol import (
    ConnectionClosedError,
    receive_message,
    send_message,
)
from spo_core.service import CorporateService, RecordNotFoundError

logger = logging.getLogger(__name__)

RESERVED_KEYS = {"UUID", "ACTION", "ID"}


class ConnectionWriter:
    """Escritor de un socket con lock compartido entre respuestas directas
    y notificaciones asincronas (Observer), para que nunca se intercalen.

    Un mismo socket puede recibir escrituras desde dos hilos distintos: el
    hilo que atiende esta conexion (respondiendo a get/set/list/subscribe) y
    cualquier otro hilo que procese un "set" de otro cliente y dispare una
    notificacion hacia este socket si esta suscripto. El lock serializa
    todas las escrituras, sin importar de donde vengan, para que nunca se
    intercalen los bytes de dos envios simultaneos.
    """

    def __init__(self, sock: socket.socket) -> None:
        """Guarda el socket y crea el lock de escritura."""
        self._sock = sock
        self._lock = threading.Lock()

    def send(self, data: dict[str, Any]) -> None:
        """Envia data al socket, serializado por el lock. Puede lanzar OSError."""
        with self._lock:
            send_message(self._sock, data)

    def send_update(self, data: dict[str, Any]) -> bool:
        """Cumple el contrato Subscriber de EventPublisher: no lanza, devuelve bool."""
        try:
            self.send(data)
            return True
        except OSError:
            logger.info("No se pudo notificar a un suscriptor (socket cerrado).")
            return False


def _build_error_response(action: str | None, client_uuid: str | None, message: str) -> dict[str, Any]:
    """Arma una respuesta de error consistente para el cliente."""
    return {"ACTION": action, "UUID": client_uuid, "ERROR": message}


def handle_connection(sock: socket.socket, service: CorporateService, *, verbose: bool = False) -> None:
    """Atiende una conexion de principio a fin: lee mensajes y despacha acciones.

    Se ejecuta en su propio hilo por conexion (ver singletonproxyobserver.py).
    Termina cuando el socket se cierra (ConnectionClosedError), dando de baja
    cualquier subscripcion activa de ese socket.
    """
    session_id = str(uuid.uuid4())
    writer = ConnectionWriter(sock)
    is_subscribed = False

    if verbose:
        logger.info("Nueva conexion. session=%s", session_id)

    try:
        while True:
            try:
                message = receive_message(sock)
            except (json.JSONDecodeError, ValueError) as err:
                writer.send(_build_error_response(None, None, f"JSON invalido: {err}"))
                continue

            client_uuid = message.get("UUID")
            action = message.get("ACTION")

            if not isinstance(client_uuid, str) or not client_uuid:
                writer.send(_build_error_response(action, client_uuid, "Falta UUID."))
                continue
            if action not in {"get", "set", "list", "subscribe"}:
                writer.send(_build_error_response(action, client_uuid, "ACTION invalida o ausente."))
                continue

            if verbose:
                logger.info("session=%s UUID=%s ACTION=%s", session_id, client_uuid, action)

            if action == "subscribe":
                service.subscribe(writer, client_uuid=client_uuid, session_id=session_id)
                is_subscribed = True
                writer.send({"ACTION": "subscribe", "UUID": client_uuid, "STATUS": "OK"})
                continue

            if action == "list":
                records = service.list_all(client_uuid=client_uuid, session_id=session_id)
                writer.send({"ACTION": "list", "UUID": client_uuid, "DATA": records})
                continue

            record_id = message.get("ID")
            if not isinstance(record_id, str) or not record_id:
                writer.send(_build_error_response(action, client_uuid, "Falta ID."))
                continue

            if action == "get":
                try:
                    record = service.get(record_id, client_uuid=client_uuid, session_id=session_id)
                    writer.send({"ACTION": "get", "UUID": client_uuid, "DATA": record})
                except RecordNotFoundError:
                    writer.send(_build_error_response(action, client_uuid, "Registro no encontrado."))
                continue

            # action == "set"
            fields = {k: v for k, v in message.items() if k not in RESERVED_KEYS}
            try:
                result = service.set(record_id, fields, client_uuid=client_uuid, session_id=session_id)
                writer.send({"ACTION": "set", "UUID": client_uuid, "DATA": result})
            except UpdateAccessError as err:
                writer.send(_build_error_response(action, client_uuid, str(err)))

    except ConnectionClosedError:
        if verbose:
            logger.info("Conexion cerrada. session=%s", session_id)
    finally:
        if is_subscribed:
            service.unsubscribe(writer)

"""Lógica de observerclient.py: se suscribe y recibe notificaciones indefinidamente."""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from spo_core.protocol import ConnectionClosedError, receive_message, send_message

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080
DEFAULT_RETRY_SECONDS = 30

Connector = Callable[[str, int], socket.socket]
SleepFunc = Callable[[float], None]


def _default_connector(host: str, port: int) -> socket.socket:
    """Abre una conexión TCP real al servidor, sin timeout de lectura.

    A diferencia de singletonclient.py (que espera una única respuesta
    inmediata), este cliente queda suscripto esperando notificaciones que
    pueden tardar minutos u horas en llegar, asi que el socket no debe
    expirar por inactividad.
    """
    sock = socket.create_connection((host, port), timeout=5)
    sock.settimeout(None)
    return sock


def _emit(data: dict[str, Any], output_path: str | None) -> None:
    """Muestra o graba una notificación recibida, según exige la consigna.

    Si hay archivo de salida, se escribe ahi Y TAMBIEN se imprime por stdout,
    ya que la consigna exige ambas salidas ("lo mostrara por el archivo output.json
    si fue informado por argumento y por salida estandar").
    """
    text = json.dumps(data, indent=2, ensure_ascii=False)
    print(text)
    if output_path is not None:
        Path(output_path).write_text(text, encoding="utf-8")


def _subscribe_and_listen(
    sock: socket.socket,
    client_uuid: str,
    output_path: str | None,
    stop_event: threading.Event,
) -> None:
    """Se suscribe y procesa mensajes hasta que la conexión se cierre o se pida parar.

    Un mensaje que no es JSON valido (json.JSONDecodeError) o que no es un
    objeto (ValueError, ver protocol.receive_message) se descarta con un aviso,
    sin cortar la conexion: solo ConnectionClosedError (socket realmente
    cerrado) dispara la reconexion en el llamador.
    """
    send_message(sock, {"UUID": client_uuid, "ACTION": "subscribe"})
    confirmation = receive_message(sock)
    _emit(confirmation, output_path)

    while not stop_event.is_set():
        try:
            message = receive_message(sock)
        except (json.JSONDecodeError, ValueError) as err:
            print(f"Mensaje invalido recibido del servidor, se descarta: {err}", file=sys.stderr)
            continue
        _emit(message, output_path)


def run_observer_client(
    client_uuid: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    output_path: str | None = None,
    *,
    retry_seconds: float = DEFAULT_RETRY_SECONDS,
    connector: Connector = _default_connector,
    sleep_func: SleepFunc = time.sleep,
    stop_event: threading.Event | None = None,
) -> int:
    """Ejecuta el flujo de observerclient.py: suscribe y escucha, con reconexión automática.

    Corre hasta que stop_event se active o hasta que el proceso sea interrumpido.
    """
    if stop_event is None:
        stop_event = threading.Event()

    while not stop_event.is_set():
        try:
            sock = connector(host, port)
        except OSError as err:
            print(f"No se pudo conectar a {host}:{port}: {err}. Reintentando en {retry_seconds}s.", file=sys.stderr)
            sleep_func(retry_seconds)
            continue

        try:
            _subscribe_and_listen(sock, client_uuid, output_path, stop_event)
        except ConnectionClosedError:
            print(f"Conexion perdida. Reintentando en {retry_seconds}s.", file=sys.stderr)
            sleep_func(retry_seconds)
        finally:
            sock.close()

    return 0

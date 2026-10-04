"""Lógica de singletonclient.py: lee un input.json, lo envía al servidor y escribe la respuesta."""

from __future__ import annotations

import json
import socket
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from spo_core.protocol import ConnectionClosedError, receive_message, send_message

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080

Connector = Callable[[str, int], socket.socket]


def _default_connector(host: str, port: int) -> socket.socket:
    """Abre una conexión TCP real al servidor."""
    return socket.create_connection((host, port), timeout=5)


def run_singleton_client(
    input_path: str,
    output_path: str | None,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    connector: Connector = _default_connector,
) -> int:
    """Ejecuta el flujo completo de singletonclient.py. Devuelve el código de salida."""
    try:
        raw_input = Path(input_path).read_text(encoding="utf-8")
    except OSError as err:
        print(f"No se pudo leer el archivo de entrada: {err}", file=sys.stderr)
        return 1

    try:
        request: Any = json.loads(raw_input)
    except json.JSONDecodeError as err:
        print(f"El archivo de entrada no contiene JSON valido: {err}", file=sys.stderr)
        return 1

    if not isinstance(request, dict):
        print("El archivo de entrada debe contener un objeto JSON.", file=sys.stderr)
        return 1

    try:
        sock = connector(host, port)
    except OSError as err:
        print(f"No se pudo conectar al servidor {host}:{port}: {err}", file=sys.stderr)
        return 1

    try:
        send_message(sock, request)
        response = receive_message(sock)
    except ConnectionClosedError as err:
        print(f"El servidor cerro la conexion inesperadamente: {err}", file=sys.stderr)
        return 1
    finally:
        sock.close()

    output_text = json.dumps(response, indent=2, ensure_ascii=False)
    if output_path is not None:
        Path(output_path).write_text(output_text, encoding="utf-8")
    else:
        print(output_text)

    return 0

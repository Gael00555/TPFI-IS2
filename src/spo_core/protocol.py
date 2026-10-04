"""Protocolo de mensajes JSON delimitados por salto de línea sobre un socket.

El enunciado no especifica como delimitar mensajes sobre el socket TCP (dato
necesario porque TCP es un flujo continuo de bytes, no mensajes discretos).
Se adopta como decision de diseño el framing mas simple que soporta conexiones
persistentes (necesario para "subscribe"): cada mensaje es un objeto JSON en
una unica linea, terminada en "\\n".
"""

from __future__ import annotations

import json
import socket
from typing import Any

ENCODING = "utf-8"
NEWLINE = b"\n"


class ConnectionClosedError(Exception):
    """Se lanza cuando el socket se cierra mientras se esperaba un mensaje."""


def send_message(sock: socket.socket, payload: dict[str, Any]) -> None:
    """Serializa payload a JSON y lo envia como una linea terminada en \\n."""
    line = json.dumps(payload) + "\n"
    sock.sendall(line.encode(ENCODING))


def _readline(sock: socket.socket) -> bytes:
    """Lee bytes del socket hasta encontrar un \\n (excluido) o hasta que se cierre."""
    buffer = bytearray()
    while True:
        chunk = sock.recv(1)
        if not chunk:
            if buffer:
                raise ConnectionClosedError("Socket cerrado a mitad de un mensaje.")
            raise ConnectionClosedError("Socket cerrado sin enviar ningun mensaje.")
        if chunk == NEWLINE:
            return bytes(buffer)
        buffer.extend(chunk)


def receive_message(sock: socket.socket) -> dict[str, Any]:
    """Lee una linea del socket y la decodifica como JSON.

    Levanta ConnectionClosedError si el socket se cierra antes de completar un
    mensaje, o json.JSONDecodeError si la linea recibida no es JSON valido.
    """
    raw_line = _readline(sock)
    decoded: Any = json.loads(raw_line.decode(ENCODING))
    if not isinstance(decoded, dict):
        raise ValueError("El mensaje recibido no es un objeto JSON.")
    return decoded

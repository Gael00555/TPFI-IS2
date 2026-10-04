"""Tests del protocolo de framing JSON sobre sockets."""

from __future__ import annotations

import json
import socket
from collections.abc import Iterator

import pytest

from spo_core.protocol import (
    ConnectionClosedError,
    receive_message,
    send_message,
)


@pytest.fixture
def socket_pair() -> Iterator[tuple[socket.socket, socket.socket]]:
    """Crea un par de sockets ya conectados entre si, en memoria."""
    left, right = socket.socketpair()
    yield left, right
    left.close()
    right.close()


def test_send_and_receive_roundtrip(socket_pair: tuple[socket.socket, socket.socket]) -> None:
    """Lo que se envia de un lado se recibe identico del otro."""
    left, right = socket_pair
    payload = {"UUID": "cpu-1", "ACTION": "get", "ID": "UADER-FCYT-IS2"}

    send_message(left, payload)
    received = receive_message(right)

    assert received == payload


def test_multiple_messages_are_framed_correctly(
    socket_pair: tuple[socket.socket, socket.socket],
) -> None:
    """Dos mensajes enviados seguidos se reciben como dos mensajes separados."""
    left, right = socket_pair

    send_message(left, {"n": 1})
    send_message(left, {"n": 2})

    assert receive_message(right) == {"n": 1}
    assert receive_message(right) == {"n": 2}


def test_receive_raises_on_closed_socket_without_data(
    socket_pair: tuple[socket.socket, socket.socket],
) -> None:
    """Si el socket se cierra sin mandar nada, se levanta ConnectionClosedError."""
    left, right = socket_pair
    left.close()

    with pytest.raises(ConnectionClosedError):
        receive_message(right)


def test_receive_raises_on_closed_socket_mid_message(
    socket_pair: tuple[socket.socket, socket.socket],
) -> None:
    """Si el socket se cierra a mitad de un mensaje (sin \\n), tambien se detecta."""
    left, right = socket_pair
    left.sendall(b'{"incompleto": tr')
    left.close()

    with pytest.raises(ConnectionClosedError):
        receive_message(right)


def test_receive_raises_on_invalid_json(
    socket_pair: tuple[socket.socket, socket.socket],
) -> None:
    """Una linea que no es JSON valido levanta json.JSONDecodeError."""
    left, right = socket_pair
    left.sendall(b"esto no es json\n")

    with pytest.raises(json.JSONDecodeError):
        receive_message(right)


def test_receive_raises_on_json_that_is_not_an_object(
    socket_pair: tuple[socket.socket, socket.socket],
) -> None:
    """Un JSON valido pero que no es un objeto (ej. una lista) se rechaza."""
    left, right = socket_pair
    left.sendall(b"[1, 2, 3]\n")

    with pytest.raises(ValueError):
        receive_message(right)

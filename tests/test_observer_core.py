"""Tests de observer_core (lógica de observerclient.py, con reconexión)."""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from spo_core.observer_core import run_observer_client
from spo_core.protocol import receive_message, send_message


def _server_thread(
    server_sock: socket.socket,
    *,
    extra_messages: list[dict[str, object]] | None = None,
    raw_before_close: bytes | None = None,
) -> threading.Thread:
    """Arranca un hilo que simula al servidor: confirma el subscribe, manda
    mensajes adicionales y cierra la conexión.
    """

    def _run() -> None:
        receive_message(server_sock)  # consume el mensaje de subscribe
        send_message(server_sock, {"ACTION": "subscribe", "STATUS": "OK"})
        for msg in extra_messages or []:
            send_message(server_sock, msg)
        if raw_before_close is not None:
            server_sock.sendall(raw_before_close)
            send_message(server_sock, {"ACTION": "change", "ID": "recovered"})
        server_sock.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


class FakeConnector:
    """Devuelve, en cada llamada, el extremo cliente de un nuevo socketpair,
    arrancando en paralelo el hilo que simula al servidor para esa conexión.
    """

    def __init__(self, servers: list[Callable[[socket.socket], threading.Thread]]) -> None:
        """Guarda la secuencia de comportamientos de servidor a usar por conexión."""
        self._servers = servers
        self.call_count = 0
        self.threads: list[threading.Thread] = []

    def __call__(self, host: str, port: int) -> socket.socket:
        """Simula connector: abre un socketpair y arranca el servidor falso correspondiente."""
        client_sock, server_sock = socket.socketpair()
        behavior = self._servers[self.call_count]
        self.call_count += 1
        self.threads.append(behavior(server_sock))
        return client_sock

    def join_all(self) -> None:
        """Espera a que todos los hilos de servidor falso terminen."""
        for thread in self.threads:
            thread.join(timeout=2)


def _stop_after(stop_event: threading.Event, n: int) -> tuple[Callable[[float], None], list[float]]:
    """Crea un sleep_func falso que activa stop_event tras la n-esima llamada.

    Esto es lo que le pone fin al bucle de reconexion infinito de
    run_observer_client en los tests: en lugar de depender del timing del
    hilo que simula al servidor, es el propio hilo principal (vía sleep_func)
    el que decide, de forma determinista, cuándo dejar de reintentar.
    """
    calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        calls.append(seconds)
        if len(calls) >= n:
            stop_event.set()

    return fake_sleep, calls


def test_subscribes_and_receives_multiple_notifications(capsys: pytest.CaptureFixture[str]) -> None:
    """Una sola conexión puede traer la confirmación y varias notificaciones."""
    notifications = [{"ACTION": "change", "ID": "r1"}, {"ACTION": "change", "ID": "r2"}]
    connector = FakeConnector([lambda sock: _server_thread(sock, extra_messages=notifications)])
    stop_event = threading.Event()
    fake_sleep, sleep_calls = _stop_after(stop_event, n=1)

    exit_code = run_observer_client(
        "cpu-obs",
        connector=connector,
        sleep_func=fake_sleep,
        stop_event=stop_event,
    )
    connector.join_all()

    assert exit_code == 0
    assert connector.call_count == 1
    assert len(sleep_calls) == 1
    captured = capsys.readouterr()
    assert '"STATUS": "OK"' in captured.out
    assert '"ID": "r1"' in captured.out
    assert '"ID": "r2"' in captured.out


def test_reconnects_after_connection_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """Si la primera conexión falla, reintenta y logra conectarse en el segundo intento."""
    succeeded = FakeConnector([lambda sock: _server_thread(sock)])
    attempts = {"n": 0}

    def connector(host: str, port: int) -> socket.socket:
        if attempts["n"] == 0:
            attempts["n"] += 1
            raise ConnectionRefusedError("servidor caido (simulado)")
        return succeeded(host, port)

    stop_event = threading.Event()
    fake_sleep, sleep_calls = _stop_after(stop_event, n=2)

    exit_code = run_observer_client(
        "cpu-obs",
        connector=connector,
        sleep_func=fake_sleep,
        stop_event=stop_event,
    )
    succeeded.join_all()

    assert exit_code == 0
    assert succeeded.call_count == 1
    assert len(sleep_calls) == 2
    captured = capsys.readouterr()
    assert '"STATUS": "OK"' in captured.out


def test_discards_malformed_message_without_disconnecting(capsys: pytest.CaptureFixture[str]) -> None:
    """Un mensaje con JSON invalido se descarta sin cortar la conexión."""
    connector = FakeConnector([lambda sock: _server_thread(sock, raw_before_close=b"esto no es json\n")])
    stop_event = threading.Event()
    fake_sleep, _ = _stop_after(stop_event, n=1)

    exit_code = run_observer_client(
        "cpu-obs",
        connector=connector,
        sleep_func=fake_sleep,
        stop_event=stop_event,
    )
    connector.join_all()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Mensaje invalido" in captured.err
    assert '"ID": "recovered"' in captured.out


def test_writes_notifications_to_output_file(tmp_path: Path) -> None:
    """Con output_path, la última notificación recibida se graba en el archivo."""
    output_file = tmp_path / "output.json"
    connector = FakeConnector([lambda sock: _server_thread(sock, extra_messages=[{"ACTION": "change", "ID": "r1"}])])
    stop_event = threading.Event()
    fake_sleep, _ = _stop_after(stop_event, n=1)

    exit_code = run_observer_client(
        "cpu-obs",
        output_path=str(output_file),
        connector=connector,
        sleep_func=fake_sleep,
        stop_event=stop_event,
    )
    connector.join_all()

    assert exit_code == 0
    saved = json.loads(output_file.read_text(encoding="utf-8"))
    assert saved == {"ACTION": "change", "ID": "r1"}

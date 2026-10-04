"""Tests de client_core (lógica de singletonclient.py)."""

from __future__ import annotations

import json
import socket
import threading
from pathlib import Path
from typing import Any

import pytest

from spo_core.client_core import run_singleton_client
from spo_core.protocol import receive_message, send_message


class FakeServer:
    """Simula un servidor mínimo: responde con un único mensaje fijo."""

    def __init__(self, response: dict[str, Any]) -> None:
        """Crea el par de sockets y arranca el hilo que simula al servidor."""
        self.client_sock, self._server_sock = socket.socketpair()
        self.received: dict[str, Any] | None = None
        self._response = response
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        """Recibe un mensaje y responde con la respuesta fija configurada."""
        self.received = receive_message(self._server_sock)
        send_message(self._server_sock, self._response)

    def connector(self, host: str, port: int) -> socket.socket:
        """Firma compatible con Connector: ignora host/port y devuelve el socket de prueba."""
        return self.client_sock

    def join(self) -> None:
        """Espera a que el hilo del servidor falso termine."""
        self._thread.join(timeout=2)


def _write_json(path: Path, data: dict[str, Any]) -> str:
    """Escribe data como JSON en path y devuelve la ruta como string."""
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_sends_input_and_prints_response(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """El cliente envía el JSON de entrada y muestra la respuesta por stdout."""
    input_path = _write_json(tmp_path / "input.json", {"UUID": "cpu-1", "ACTION": "get", "ID": "x"})
    server = FakeServer({"ACTION": "get", "UUID": "cpu-1", "DATA": {"id": "x"}})

    exit_code = run_singleton_client(input_path, None, connector=server.connector)
    server.join()

    assert exit_code == 0
    assert server.received == {"UUID": "cpu-1", "ACTION": "get", "ID": "x"}
    captured = capsys.readouterr()
    assert '"id": "x"' in captured.out


def test_writes_response_to_output_file(tmp_path: Path) -> None:
    """Con -o, la respuesta se escribe en el archivo indicado en lugar de stdout."""
    input_path = _write_json(tmp_path / "input.json", {"UUID": "cpu-1", "ACTION": "list"})
    output_path = tmp_path / "output.json"
    server = FakeServer({"ACTION": "list", "UUID": "cpu-1", "DATA": []})

    exit_code = run_singleton_client(input_path, str(output_path), connector=server.connector)
    server.join()

    assert exit_code == 0
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved == {"ACTION": "list", "UUID": "cpu-1", "DATA": []}


def test_missing_input_file_returns_error(tmp_path: Path) -> None:
    """Si el archivo de entrada no existe, el cliente termina con error controlado."""
    missing_path = str(tmp_path / "no-existe.json")

    exit_code = run_singleton_client(missing_path, None)

    assert exit_code != 0


def test_invalid_json_input_returns_error(tmp_path: Path) -> None:
    """Si el archivo de entrada no es JSON válido, el cliente termina con error controlado."""
    input_path = tmp_path / "input.json"
    input_path.write_text("esto no es json", encoding="utf-8")

    exit_code = run_singleton_client(str(input_path), None)

    assert exit_code != 0


def test_connection_refused_returns_error(tmp_path: Path) -> None:
    """Si el servidor esta caído (conexión rechazada), el cliente termina con error controlado."""
    input_path = _write_json(tmp_path / "input.json", {"UUID": "cpu-1", "ACTION": "get", "ID": "x"})

    def failing_connector(host: str, port: int) -> socket.socket:
        raise ConnectionRefusedError("servidor caido (simulado)")

    exit_code = run_singleton_client(input_path, None, connector=failing_connector)

    assert exit_code != 0

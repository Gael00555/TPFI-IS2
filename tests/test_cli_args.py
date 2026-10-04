"""Tests del parseo de argumentos de línea de comandos."""

from __future__ import annotations

import pytest

from spo_core.cli_args import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    parse_observerclient_args,
    parse_server_args,
    parse_singletonclient_args,
)

# --- singletonclient.py -----------------------------------------------------


def test_singletonclient_minimal_args() -> None:
    """Con solo -i, output queda None y verbose en False."""
    args = parse_singletonclient_args(["-i=input.json"])

    assert args.input_path == "input.json"
    assert args.output_path is None
    assert args.verbose is False


def test_singletonclient_all_args() -> None:
    """Con -i, -o y -v, los tres quedan seteados."""
    args = parse_singletonclient_args(["-i=input.json", "-o=output.json", "-v"])

    assert args.input_path == "input.json"
    assert args.output_path == "output.json"
    assert args.verbose is True


def test_singletonclient_missing_required_input_exits() -> None:
    """Sin -i (obligatorio), el programa debe terminar con error (argumento malformado)."""
    with pytest.raises(SystemExit):
        parse_singletonclient_args([])


# --- observerclient.py -------------------------------------------------------


def test_observerclient_defaults() -> None:
    """Sin argumentos, usa host y puerto por defecto (localhost:8080)."""
    args = parse_observerclient_args([])

    assert args.host == DEFAULT_HOST
    assert args.port == DEFAULT_PORT
    assert args.output_path is None
    assert args.verbose is False


def test_observerclient_custom_host_and_port() -> None:
    """Con -s y -p, se sobreescriben host y puerto."""
    args = parse_observerclient_args(["-s=192.168.0.10", "-p=9090"])

    assert args.host == "192.168.0.10"
    assert args.port == 9090


def test_observerclient_invalid_port_exits() -> None:
    """Un puerto no numérico es un argumento malformado y debe fallar."""
    with pytest.raises(SystemExit):
        parse_observerclient_args(["-p=no-es-un-numero"])


# --- singletonproxyobserver.py ------------------------------------------------


def test_server_args_defaults() -> None:
    """Sin argumentos, usa el puerto por defecto 8080 y verbose en False."""
    args = parse_server_args([])

    assert args.port == DEFAULT_PORT
    assert args.verbose is False


def test_server_args_custom_port_and_verbose() -> None:
    """Con -p y -v, se sobreescribe el puerto y se activa verbose."""
    args = parse_server_args(["-p=9090", "-v"])

    assert args.port == 9090
    assert args.verbose is True


def test_server_args_invalid_port_exits() -> None:
    """Un puerto no numérico es un argumento malformado y debe fallar."""
    with pytest.raises(SystemExit):
        parse_server_args(["-p=no-es-un-numero"])

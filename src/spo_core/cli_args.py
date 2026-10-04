"""Parseo de argumentos de línea de comandos para los tres programas del TP."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080


@dataclass(frozen=True, slots=True)
class SingletonClientArgs:
    """Argumentos parseados para singletonclient.py."""

    input_path: str
    output_path: str | None
    verbose: bool


@dataclass(frozen=True, slots=True)
class ObserverClientArgs:
    """Argumentos parseados para observerclient.py."""

    host: str
    port: int
    output_path: str | None
    verbose: bool


@dataclass(frozen=True, slots=True)
class ServerArgs:
    """Argumentos parseados para singletonproxyobserver.py."""

    port: int
    verbose: bool


def parse_singletonclient_args(argv: list[str]) -> SingletonClientArgs:
    """Parsea: python singletonclient.py -i=input.json {-o=output.json} {-v}."""
    parser = argparse.ArgumentParser(prog="singletonclient.py")
    parser.add_argument("-i", dest="input_path", required=True)
    parser.add_argument("-o", dest="output_path", default=None)
    parser.add_argument("-v", dest="verbose", action="store_true")

    parsed = parser.parse_args(argv)
    return SingletonClientArgs(
        input_path=parsed.input_path,
        output_path=parsed.output_path,
        verbose=parsed.verbose,
    )


def parse_observerclient_args(argv: list[str]) -> ObserverClientArgs:
    """Parsea: python observerclient.py {-s=host} {-p=port} {-o=output.json} {-v}."""
    parser = argparse.ArgumentParser(prog="observerclient.py")
    parser.add_argument("-s", dest="host", default=DEFAULT_HOST)
    parser.add_argument("-p", dest="port", type=int, default=DEFAULT_PORT)
    parser.add_argument("-o", dest="output_path", default=None)
    parser.add_argument("-v", dest="verbose", action="store_true")

    parsed = parser.parse_args(argv)
    return ObserverClientArgs(
        host=parsed.host,
        port=parsed.port,
        output_path=parsed.output_path,
        verbose=parsed.verbose,
    )


def parse_server_args(argv: list[str]) -> ServerArgs:
    """Parsea: python singletonproxyobserver.py {-p=port} {-v}."""
    parser = argparse.ArgumentParser(prog="singletonproxyobserver.py")
    parser.add_argument("-p", dest="port", type=int, default=DEFAULT_PORT)
    parser.add_argument("-v", dest="verbose", action="store_true")

    parsed = parser.parse_args(argv)
    return ServerArgs(port=parsed.port, verbose=parsed.verbose)

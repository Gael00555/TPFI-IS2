"""Servidor TCP real: arma socketserver.ThreadingTCPServer y el entrypoint CLI."""

from __future__ import annotations

import logging
import socketserver
import sys
from typing import cast

from spo_core.cli_args import parse_server_args
from spo_core.server_core import handle_connection
from spo_core.service import CorporateService

logger = logging.getLogger(__name__)


class _RequestHandler(socketserver.BaseRequestHandler):
    """Delega cada conexion aceptada a handle_connection (server_core)."""

    def handle(self) -> None:
        """Atiende la conexion actual hasta que el cliente la cierre."""
        server = cast("SingletonProxyObserverServer", self.server)
        handle_connection(self.request, server.service, verbose=server.verbose)


class SingletonProxyObserverServer(socketserver.ThreadingTCPServer):
    """Servidor TCP multi-hilo: una conexion nueva -> un hilo nuevo.

    allow_reuse_address se deja en False (valor heredado de TCPServer) de forma
    intencional: es lo que permite que un segundo intento de bind en el mismo
    puerto falle con OSError, cumpliendo el requisito de la consigna de
    detectar el intento de levantar el servidor dos veces.
    """

    daemon_threads = True

    def __init__(self, port: int, service: CorporateService, *, verbose: bool = False) -> None:
        """Crea y liga el socket de escucha en el puerto indicado."""
        self.service = service
        self.verbose = verbose
        super().__init__(("", port), _RequestHandler)


def configure_logging(*, verbose: bool) -> None:
    """Configura logging a stdout, segun el flag -v (requisito de la consigna)."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )


def main(argv: list[str]) -> int:
    """Punto de entrada de singletonproxyobserver.py. Devuelve el codigo de salida."""
    args = parse_server_args(argv)
    configure_logging(verbose=args.verbose)

    try:
        server = SingletonProxyObserverServer(args.port, CorporateService(), verbose=args.verbose)
    except OSError as err:
        print(f"No se pudo iniciar el servidor en el puerto {args.port}: {err}", file=sys.stderr)
        return 1

    print(f"Servidor escuchando en el puerto {args.port}. Ctrl+C para detener.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Deteniendo el servidor...")
    finally:
        server.shutdown()
        server.server_close()
    return 0

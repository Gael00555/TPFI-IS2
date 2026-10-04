#!/usr/bin/env python
"""Punto de entrada: python observerclient.py {-s=host} {-p=port} {-o=output.json} {-v}."""

import logging
import sys
import uuid

from spo_core.cli_args import parse_observerclient_args
from spo_core.observer_core import run_observer_client

if __name__ == "__main__":
    args = parse_observerclient_args(sys.argv[1:])
    if args.verbose:
        logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    client_uuid = str(uuid.getnode())
    sys.exit(
        run_observer_client(
            client_uuid,
            host=args.host,
            port=args.port,
            output_path=args.output_path,
        )
    )

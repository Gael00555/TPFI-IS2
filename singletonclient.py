#!/usr/bin/env python
"""Punto de entrada: python singletonclient.py -i=input.json {-o=output.json} {-v}."""

import logging
import sys

from spo_core.cli_args import parse_singletonclient_args
from spo_core.client_core import run_singleton_client

if __name__ == "__main__":
    args = parse_singletonclient_args(sys.argv[1:])
    if args.verbose:
        logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    sys.exit(run_singleton_client(args.input_path, args.output_path))

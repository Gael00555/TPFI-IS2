#!/usr/bin/env python
"""Punto de entrada: python singletonproxyobserver.py {-p=port} {-v}."""

import sys

from spo_core.server_app import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
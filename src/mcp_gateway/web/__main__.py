"""Entrypoint for running the admin web console module."""

import sys
from . import run_server

if __name__ == "__main__":
    host = "127.0.0.1"
    port = 8080
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(host=host, port=port)

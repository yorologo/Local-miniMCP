"""Entrypoint for running the admin web console module."""

import os
import sys
from . import run_server

if __name__ == "__main__":
    host = os.environ.get("MCP_ADMIN_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_ADMIN_PORT", "8080"))
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(host=host, port=port)

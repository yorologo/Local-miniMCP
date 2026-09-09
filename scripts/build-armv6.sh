#!/usr/bin/env bash
set -euo pipefail

# scripts/build-armv6.sh
# Reproducible cross-compilation script for ARMv6 MCP Gateway Adapter

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC_DIR="${REPO_ROOT}/mcp-adapter"
OUTPUT="${1:-${SRC_DIR}/mcp-gateway-adapter}"

echo "Building MCP Gateway Adapter for ARMv6..."
echo "Source:  ${SRC_DIR}"
echo "Output:  ${OUTPUT}"

cd "${SRC_DIR}"
CGO_ENABLED=0 GOOS=linux GOARCH=arm GOARM=6 go build -ldflags="-s -w" -o "${OUTPUT}" .

echo "Build successful: $(ls -lh "${OUTPUT}")"
sha256sum "${OUTPUT}"

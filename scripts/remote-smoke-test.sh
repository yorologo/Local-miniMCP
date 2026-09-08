#!/data/data/com.termux/files/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -f "${PROJECT_ROOT}/.mcp-pi.local.env" ]; then
    set -a
    source "${PROJECT_ROOT}/.mcp-pi.local.env"
    set +a
fi

PI_HOST="${MCP_PI_HOST:-192.168.68.85}"
PI_USER="${MCP_PI_USER:-Yorologo}"
REMOTE_DIR="/home/mcp-gateway/mcp-gateway"
CFG="${REMOTE_DIR}/config/targets.local.json"

run_remote() {
    local cmd="$1"
    SSHPASS="${MCP_PI_PASSWORD:-}" sshpass -e ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" "sudo -u mcp-gateway PYTHONPATH='${REMOTE_DIR}/src' python3 -m mcp_gateway.cli --config '${CFG}' ${cmd}"
}

echo "=== 1. LIVE INTEGRATION TESTS ==="
echo "--- 1.1 health ---"
run_remote "health"

echo "--- 1.2 list-targets ---"
run_remote "list-targets"

echo "--- 1.3 target-status termux-main ---"
run_remote "target-status termux-main"

echo "--- 1.4 list-directory termux-main MCP_Local . ---"
run_remote "list-directory termux-main MCP_Local ."

echo "--- 1.5 file-stat termux-main MCP_Local README.md ---"
run_remote "file-stat termux-main MCP_Local README.md"

echo "--- 1.6 read-file termux-main MCP_Local README.md ---"
run_remote "read-file termux-main MCP_Local README.md"

echo "--- 1.7 git-status termux-main MCP_Local ---"
run_remote "git-status termux-main MCP_Local"

echo "--- 1.8 run-task termux-main MCP_Local git_status ---"
run_remote "run-task termux-main MCP_Local git_status"

echo ""
echo "=== 2. NEGATIVE TESTS ==="

echo "--- 2.1 Traversal rejection (../.bashrc) ---"
run_remote "read-file termux-main MCP_Local ../.bashrc" || true

echo "--- 2.2 Absolute path rejection (/etc/passwd) ---"
run_remote "read-file termux-main MCP_Local /etc/passwd" || true

echo "--- 2.3 Unknown task rejection (rm_rf) ---"
run_remote "run-task termux-main MCP_Local rm_rf" || true

echo "--- 2.4 Unknown target rejection (unknown-box) ---"
run_remote "target-status unknown-box" || true

echo "--- 2.5 Symlink escape rejection ---"
# Setup symlink inside MCP_Local pointing outside root
ln -sf /data/data/com.termux/files/home "${PROJECT_ROOT}/escape_symlink_test"
run_remote "read-file termux-main MCP_Local escape_symlink_test/.bashrc" || true
rm -f "${PROJECT_ROOT}/escape_symlink_test"

echo "=== ALL SMOKE TESTS EXECUTED ==="

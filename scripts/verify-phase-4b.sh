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

echo "=== EXECUTING PHASE 4B VERIFICATION SUITE ON MCP-PI (${PI_HOST}) ==="

SSHPASS="${MCP_PI_PASSWORD:-}" sshpass -e ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" "
    echo '=== 1. SYSTEMD SERVICE STATUS ==='
    systemctl status mcp-gateway-admin | head -8

    echo ''
    echo '=== 2. LOCALHOST PORT BINDING ==='
    sudo ss -tulpn | grep 8080

    echo ''
    echo '=== 3. RUNNING REMOTE VERIFICATION SCRIPT ==='
    sudo -u mcp-gateway python3 /home/mcp-gateway/mcp-gateway/scripts/remote_verify.py

    echo ''
    echo '=== 4. RESOURCE MEASUREMENTS ==='
    PID=\$(pgrep -f 'mcp_gateway.web' | head -1)
    echo '--- Admin Web Process (PID: '\$PID') ---'
    ps -o pid,user,vsz,rss,comm -p \"\$PID\"
    echo '--- Memory ---'
    free -m
    echo '--- Database Size ---'
    sudo ls -lh /home/mcp-gateway/.local/share/mcp-gateway/gateway.db
    echo '--- Localhost Login Latency ---'
    curl -o /dev/null -s -w 'Time total: %{time_total}s | HTTP code: %{http_code}\n' http://127.0.0.1:8080/login
"

echo "=== ALL PHASE 4B VERIFICATIONS COMPLETED ==="

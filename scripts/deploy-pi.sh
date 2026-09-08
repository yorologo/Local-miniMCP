#!/data/data/com.termux/files/usr/bin/env bash
set -euo pipefail

# Deployment script for MCP Gateway on MCP-Pi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source local credentials if present
if [ -f "${PROJECT_ROOT}/.mcp-pi.local.env" ]; then
    set -a
    source "${PROJECT_ROOT}/.mcp-pi.local.env"
    set +a
fi

PI_HOST="${MCP_PI_HOST:-192.168.68.85}"
PI_USER="${MCP_PI_USER:-Yorologo}"
REMOTE_TARGET_DIR="/home/mcp-gateway/mcp-gateway"

echo "=== Deploying MCP Gateway to MCP-Pi (${PI_HOST}) ==="

# Check targets.local.json exists
if [ ! -f "${PROJECT_ROOT}/config/targets.local.json" ]; then
    echo "ERROR: ${PROJECT_ROOT}/config/targets.local.json not found."
    exit 1
fi

# Prepare remote directory structure
echo "1. Creating remote directory structure..."
SSHPASS="${MCP_PI_PASSWORD:-}" sshpass -e ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" "
    sudo -u mcp-gateway mkdir -p '${REMOTE_TARGET_DIR}/src/mcp_gateway' '${REMOTE_TARGET_DIR}/config' '${REMOTE_TARGET_DIR}/tests' '${REMOTE_TARGET_DIR}/scripts' '${REMOTE_TARGET_DIR}/bin' '${REMOTE_TARGET_DIR}/docs' '/home/mcp-gateway/.local/share/mcp-gateway' '/home/mcp-gateway/.config/mcp-gateway'
    sudo chmod 700 '/home/mcp-gateway/.local/share/mcp-gateway' '/home/mcp-gateway/.config/mcp-gateway'
"

# Tar and stream codebase to remote directory
echo "2. Transferring source and config files..."
tar -C "${PROJECT_ROOT}" -czf - src config tests scripts docs | \
    SSHPASS="${MCP_PI_PASSWORD:-}" sshpass -e ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" "
        sudo -u mcp-gateway tar -xzf - -C '${REMOTE_TARGET_DIR}'
        sudo chown -R mcp-gateway:mcp-gateway '${REMOTE_TARGET_DIR}'
        sudo chmod -R u+rwX,go+rX '${REMOTE_TARGET_DIR}'
    "

# Transfer Go MCP adapter binary if present
if [ -f "${PROJECT_ROOT}/mcp-adapter/mcp-gateway-adapter" ]; then
    echo "2a. Transferring Go MCP adapter binary..."
    cat "${PROJECT_ROOT}/mcp-adapter/mcp-gateway-adapter" | \
        SSHPASS="${MCP_PI_PASSWORD:-}" sshpass -e ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" "
            sudo -u mcp-gateway tee '${REMOTE_TARGET_DIR}/bin/mcp-gateway-adapter' > /dev/null
            sudo chmod 755 '${REMOTE_TARGET_DIR}/bin/mcp-gateway-adapter'
        "
fi

# Configure systemd services
echo "2b. Configuring systemd services..."
SSHPASS="${MCP_PI_PASSWORD:-}" sshpass -e ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" "
    sudo cp '${REMOTE_TARGET_DIR}/config/systemd/mcp-gateway-admin.service' /etc/systemd/system/mcp-gateway-admin.service
    if [ -f '${REMOTE_TARGET_DIR}/config/systemd/mcp-gateway-mcp.service' ]; then
        sudo cp '${REMOTE_TARGET_DIR}/config/systemd/mcp-gateway-mcp.service' /etc/systemd/system/mcp-gateway-mcp.service
    fi
    sudo systemctl daemon-reload
    sudo systemctl restart mcp-gateway-admin
    if [ -f '/etc/systemd/system/mcp-gateway-mcp.service' ]; then
        sudo systemctl enable mcp-gateway-mcp
        sudo systemctl restart mcp-gateway-mcp
    fi
"

# Verify remote deployment and run tests as mcp-gateway
echo "3. Running remote unit tests as mcp-gateway..."
SSHPASS="${MCP_PI_PASSWORD:-}" sshpass -e ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" "
    sudo -u mcp-gateway python3 -m unittest discover -s '${REMOTE_TARGET_DIR}/tests' -p 'test_*.py' -v
"

echo "=== Deployment and remote tests completed successfully ==="

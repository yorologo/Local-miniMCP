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
tar -C "${PROJECT_ROOT}" -czf - src config tests scripts docs bin compatibility.json manifest.json install.sh SHA256SUMS | \
    SSHPASS="${MCP_PI_PASSWORD:-}" sshpass -e ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" "
        sudo -u mcp-gateway tar -xzf - -C '${REMOTE_TARGET_DIR}'
        sudo chown -R mcp-gateway:mcp-gateway '${REMOTE_TARGET_DIR}'
        sudo chmod -R u+rwX,go+rX '${REMOTE_TARGET_DIR}'
        sudo chmod 755 '${REMOTE_TARGET_DIR}/bin/mcp-gateway' '${REMOTE_TARGET_DIR}/install.sh'
    "

# Transfer Go MCP adapter binary if present and changed
if [ -f "${PROJECT_ROOT}/mcp-adapter/mcp-gateway-adapter" ]; then
    LOCAL_BIN_SHA=$(sha256sum "${PROJECT_ROOT}/mcp-adapter/mcp-gateway-adapter" | awk '{print $1}')
    REMOTE_BIN_SHA=$(SSHPASS="${MCP_PI_PASSWORD:-}" sshpass -e ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" "sha256sum '${REMOTE_TARGET_DIR}/bin/mcp-gateway-adapter' 2>/dev/null | awk '{print \$1}'" || true)

    if [ "${LOCAL_BIN_SHA}" != "${REMOTE_BIN_SHA}" ]; then
        echo "2a. Transferring Go MCP adapter binary (checksum mismatch)..."
        SSHPASS="${MCP_PI_PASSWORD:-}" sshpass -e ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" "
            sudo systemctl stop mcp-gateway-mcp 2>/dev/null || true
        "
        SSHPASS="${MCP_PI_PASSWORD:-}" sshpass -e scp -O -o StrictHostKeyChecking=accept-new "${PROJECT_ROOT}/mcp-adapter/mcp-gateway-adapter" "${PI_USER}@${PI_HOST}:/tmp/mcp-gateway-adapter.tmp"
        SSHPASS="${MCP_PI_PASSWORD:-}" sshpass -e ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" "
            sudo mv -f /tmp/mcp-gateway-adapter.tmp '${REMOTE_TARGET_DIR}/bin/mcp-gateway-adapter'
            sudo chown mcp-gateway:mcp-gateway '${REMOTE_TARGET_DIR}/bin/mcp-gateway-adapter'
            sudo chmod 755 '${REMOTE_TARGET_DIR}/bin/mcp-gateway-adapter'
        "
    else
        echo "2a. Go MCP adapter binary is up to date (${LOCAL_BIN_SHA:0:8})."
    fi
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

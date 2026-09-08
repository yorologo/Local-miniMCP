#!/bin/sh
# Idempotent Installer for MCP Raspberry Pi Gateway
set -eu

echo "=================================================="
echo "=== MCP Gateway Idempotent Installer          ==="
echo "=================================================="

# 1. Preflight & Architecture
ARCH=$(uname -m)
echo "[1/8] Verifying system architecture: ${ARCH}..."
case "${ARCH}" in
    armv6*|armv7*|aarch64|x86_64)
        echo "      Architecture supported."
        ;;
    *)
        echo "      WARNING: Architecture ${ARCH} may require custom compilation."
        ;;
esac

# 2. Dependencies Check
echo "[2/8] Checking dependencies (python3, sqlite3)..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required but not installed." >&2
    exit 1
fi

PY_OK=$(python3 -c "import sys; print(1 if sys.version_info >= (3, 9) else 0)")
if [ "${PY_OK}" != "1" ]; then
    echo "ERROR: Python 3.9 or higher is required." >&2
    exit 1
fi

# 3. Service User Verification
echo "[3/8] Checking service user (mcp-gateway)..."
if id -u mcp-gateway >/dev/null 2>&1; then
    echo "      User 'mcp-gateway' exists."
else
    if [ "$(id -u)" = "0" ]; then
        echo "      Creating service user 'mcp-gateway'..."
        useradd -r -s /bin/bash -m -d /home/mcp-gateway mcp-gateway
    else
        echo "      NOTICE: Not running as root; skipping useradd."
    fi
fi

# 4. Target Directories Setup
INSTALL_DIR="/home/mcp-gateway/mcp-gateway"
DATA_DIR="/home/mcp-gateway/.local/share/mcp-gateway"
CONFIG_DIR="/home/mcp-gateway/.config/mcp-gateway"
BIN_DIR="/usr/local/bin"

echo "[4/8] Setting up directory layout..."
mkdir -p "${INSTALL_DIR}/bin" "${INSTALL_DIR}/src" "${INSTALL_DIR}/config" "${DATA_DIR}/backups" "${CONFIG_DIR}"

if [ "$(id -u)" = "0" ] && id -u mcp-gateway >/dev/null 2>&1; then
    chmod 700 "${DATA_DIR}" "${CONFIG_DIR}"
    chown -R mcp-gateway:mcp-gateway "${INSTALL_DIR}" "${DATA_DIR}" "${CONFIG_DIR}"
fi

# 5. Database Initialization (Non-destructive)
echo "[5/8] Verifying database..."
DB_PATH="${DATA_DIR}/gateway.db"
if [ ! -f "${DB_PATH}" ]; then
    echo "      Initializing new SQLite database at ${DB_PATH}..."
    if [ "$(id -u)" = "0" ] && id -u mcp-gateway >/dev/null 2>&1; then
        sudo -u mcp-gateway MCP_GATEWAY_DB="${DB_PATH}" PYTHONPATH="${INSTALL_DIR}/src" python3 -c "from mcp_gateway.schema import init_db; init_db('${DB_PATH}')"
    else
        MCP_GATEWAY_DB="${DB_PATH}" PYTHONPATH="${INSTALL_DIR}/src" python3 -c "from mcp_gateway.schema import init_db; init_db('${DB_PATH}')" || true
    fi
else
    echo "      Preserving existing database at ${DB_PATH}."
fi

# 6. Install CLI Wrapper
echo "[6/8] Installing CLI wrapper..."
if [ -f "${INSTALL_DIR}/bin/mcp-gateway" ] && [ "$(id -u)" = "0" ]; then
    ln -sf "${INSTALL_DIR}/bin/mcp-gateway" "${BIN_DIR}/mcp-gateway"
    chmod 755 "${BIN_DIR}/mcp-gateway"
fi

# 7. Systemd Services
echo "[7/8] Configuring systemd services..."
if [ "$(id -u)" = "0" ] && command -v systemctl >/dev/null 2>&1; then
    if [ -f "${INSTALL_DIR}/config/systemd/mcp-gateway-admin.service" ]; then
        cp "${INSTALL_DIR}/config/systemd/mcp-gateway-admin.service" /etc/systemd/system/mcp-gateway-admin.service
    fi
    if [ -f "${INSTALL_DIR}/config/systemd/mcp-gateway-mcp.service" ]; then
        cp "${INSTALL_DIR}/config/systemd/mcp-gateway-mcp.service" /etc/systemd/system/mcp-gateway-mcp.service
    fi
    systemctl daemon-reload
    systemctl enable mcp-gateway-admin mcp-gateway-mcp 2>/dev/null || true
    systemctl restart mcp-gateway-admin mcp-gateway-mcp 2>/dev/null || true
fi

# 8. Post-install Doctor
echo "[8/8] Executing post-installation diagnostics..."
if [ -f "${INSTALL_DIR}/bin/mcp-gateway" ]; then
    "${INSTALL_DIR}/bin/mcp-gateway" doctor || true
fi

echo "=================================================="
echo "=== Installation complete.                     ==="
echo "=================================================="

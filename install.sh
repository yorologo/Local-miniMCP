#!/bin/sh
# Idempotent bootstrap installer for the MCP Gateway appliance.
set -eu

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

warn() {
    echo "WARNING: $*" >&2
}

echo "=================================================="
echo "=== MCP Gateway Idempotent Installer          ==="
echo "=================================================="

# This installer manages a system account and systemd units, so root is required.
[ "$(id -u)" = "0" ] || fail "install.sh must run as root (for example: sudo ./install.sh)"

# 1. Preflight & Architecture
ARCH=$(uname -m)
echo "[1/8] Verifying system architecture: ${ARCH}..."
case "${ARCH}" in
    armv6*|armv7*|aarch64|x86_64)
        echo "      Architecture supported."
        ;;
    *)
        warn "Architecture ${ARCH} is not in the verified compatibility set; custom validation may be required."
        ;;
esac

# 2. Required dependencies and runtime
echo "[2/8] Checking required runtime dependencies..."
for cmd in python3 systemctl useradd install; do
    command -v "${cmd}" >/dev/null 2>&1 || fail "${cmd} is required but not installed"
done

PY_OK=$(python3 -c "import sys; print(1 if sys.version_info >= (3, 9) else 0)")
[ "${PY_OK}" = "1" ] || fail "Python 3.9 or higher is required"
python3 -c "import sqlite3, flask, werkzeug" >/dev/null 2>&1 || \
    fail "Python runtime dependencies are missing; install the external packages declared in requirements.txt"

# 3. Service user
echo "[3/8] Checking service user (mcp-gateway)..."
if id -u mcp-gateway >/dev/null 2>&1; then
    echo "      User 'mcp-gateway' exists."
else
    echo "      Creating service user 'mcp-gateway'..."
    useradd -r -s /bin/bash -m -d /home/mcp-gateway mcp-gateway
fi

# 4. Directory layout and required source files
INSTALL_DIR="/home/mcp-gateway/mcp-gateway"
DATA_DIR="/home/mcp-gateway/.local/share/mcp-gateway"
CONFIG_DIR="/home/mcp-gateway/.config/mcp-gateway"
BIN_DIR="/usr/local/bin"

echo "[4/8] Setting up directory layout..."
mkdir -p "${INSTALL_DIR}/bin" "${INSTALL_DIR}/src" "${INSTALL_DIR}/config" "${DATA_DIR}/backups" "${CONFIG_DIR}"
chmod 700 "${DATA_DIR}" "${CONFIG_DIR}"
chown -R mcp-gateway:mcp-gateway "${INSTALL_DIR}" "${DATA_DIR}" "${CONFIG_DIR}"

[ -f "${INSTALL_DIR}/bin/mcp-gateway" ] || fail "Required CLI wrapper is missing: ${INSTALL_DIR}/bin/mcp-gateway"
for unit in mcp-gateway-admin.service mcp-gateway-mcp.service; do
    [ -f "${INSTALL_DIR}/config/systemd/${unit}" ] || fail "Required systemd unit is missing: ${unit}"
done

# 5. Database initialization / migration
echo "[5/8] Verifying database..."
DB_PATH="${DATA_DIR}/gateway.db"
if [ ! -f "${DB_PATH}" ]; then
    echo "      Initializing new SQLite database at ${DB_PATH}..."
else
    echo "      Preserving and migrating existing database at ${DB_PATH}."
fi
sudo -u mcp-gateway MCP_GATEWAY_DB="${DB_PATH}" PYTHONPATH="${INSTALL_DIR}/src" \
    python3 -c "from mcp_gateway.schema import init_db; init_db('${DB_PATH}')"

# 6. CLI wrapper
echo "[6/8] Installing CLI wrapper..."
ln -sf "${INSTALL_DIR}/bin/mcp-gateway" "${BIN_DIR}/mcp-gateway"
chmod 755 "${BIN_DIR}/mcp-gateway"

# 7. Required systemd services
echo "[7/8] Configuring systemd services..."
install -m 0644 "${INSTALL_DIR}/config/systemd/mcp-gateway-admin.service" /etc/systemd/system/mcp-gateway-admin.service
install -m 0644 "${INSTALL_DIR}/config/systemd/mcp-gateway-mcp.service" /etc/systemd/system/mcp-gateway-mcp.service
systemctl daemon-reload
systemctl enable mcp-gateway-admin mcp-gateway-mcp >/dev/null
systemctl restart mcp-gateway-admin mcp-gateway-mcp
systemctl is-active --quiet mcp-gateway-admin || fail "mcp-gateway-admin did not become active"
systemctl is-active --quiet mcp-gateway-mcp || fail "mcp-gateway-mcp did not become active"

# The MCP adapter is intentionally slow on constrained ARMv6 hardware; wait for readiness.
ready=0
i=1
while [ "${i}" -le 45 ]; do
    if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/ready', timeout=2).read()" >/dev/null 2>&1; then
        ready=1
        break
    fi
    i=$((i + 1))
    sleep 1
done
[ "${ready}" = "1" ] || fail "mcp-gateway-mcp did not become ready within 45 seconds"

# 8. Post-install Doctor is a required gate for a successful appliance install.
echo "[8/8] Executing post-installation diagnostics..."
sudo -u mcp-gateway "${INSTALL_DIR}/bin/mcp-gateway" doctor

echo "=================================================="
echo "=== Installation complete and verified.        ==="
echo "=================================================="

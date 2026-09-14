#!/data/data/com.termux/files/usr/bin/env bash
set -euo pipefail

# Deterministic deployment for MCP-Pi from the Termux development checkout.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

command -v git >/dev/null 2>&1 || { echo "ERROR: git is required for deterministic deployment" >&2; exit 1; }
DEPLOY_SHA="$(git -C "${PROJECT_ROOT}" rev-parse HEAD)"
DEPLOY_BRANCH="$(git -C "${PROJECT_ROOT}" branch --show-current)"
if ! git -C "${PROJECT_ROOT}" diff --quiet || ! git -C "${PROJECT_ROOT}" diff --cached --quiet; then
    echo "ERROR: deployment requires a clean Git working tree" >&2
    exit 1
fi

if [ -f "${PROJECT_ROOT}/.mcp-pi.local.env" ]; then
    set -a
    source "${PROJECT_ROOT}/.mcp-pi.local.env"
    set +a
fi

PI_HOST="${MCP_PI_HOST:-192.168.68.55}"
PI_USER="${MCP_PI_USER:-yorologo}"
PI_IDENTITY_FILE="${MCP_PI_IDENTITY_FILE:-${HOME}/.ssh/id_rsa}"
REMOTE_TARGET_DIR="/home/mcp-gateway/mcp-gateway"
TMP_BASE="${TMPDIR:-${PREFIX:-/data/data/com.termux/files/usr}/tmp}"

SSH_OPTS=(
    -i "${PI_IDENTITY_FILE}"
    -o BatchMode=yes
    -o StrictHostKeyChecking=yes
)

ssh_pi() {
    ssh "${SSH_OPTS[@]}" "${PI_USER}@${PI_HOST}" "$@"
}

scp_pi() {
    scp -O "${SSH_OPTS[@]}" "$@"
}

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

[ -f "${PROJECT_ROOT}/config/targets.local.json" ] || fail "config/targets.local.json not found"
[ -r "${PI_IDENTITY_FILE}" ] || fail "SSH identity not readable: ${PI_IDENTITY_FILE}"
command -v go >/dev/null 2>&1 || fail "Go is required to build the ARMv6 MCP adapter"
command -v tar >/dev/null 2>&1 || fail "tar is required"
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is required"
mkdir -p "${TMP_BASE}"

ADAPTER_STAGE="$(mktemp "${TMP_BASE}/mcp-gateway-adapter.XXXXXX")"
STRINGS_STAGE="${ADAPTER_STAGE}.strings"
trap 'rm -f "${ADAPTER_STAGE}" "${STRINGS_STAGE}"' EXIT

echo "=== Deploying MCP Gateway to MCP-Pi (${PI_USER}@${PI_HOST}) ==="

echo "1. Building and validating ARMv6 MCP adapter from current source..."
(
    cd "${PROJECT_ROOT}/mcp-adapter"
    GOOS=linux GOARCH=arm GOARM=6 CGO_ENABLED=0 \
        go build -trimpath -ldflags='-s -w' -o "${ADAPTER_STAGE}" .
)
file "${ADAPTER_STAGE}" | grep -Eq 'ELF 32-bit.*ARM' || fail "adapter is not a Linux ARMv6-compatible ELF"
strings "${ADAPTER_STAGE}" > "${STRINGS_STAGE}"
grep -Fq -- 'auth-token-file' "${STRINGS_STAGE}" || fail "adapter source/build is missing -auth-token-file"
grep -Fq -- 'client-id' "${STRINGS_STAGE}" || fail "adapter source/build is missing -client-id"
LOCAL_BIN_SHA="$(sha256sum "${ADAPTER_STAGE}" | awk '{print $1}')"
echo "   adapter sha256=${LOCAL_BIN_SHA}"

echo "2. Verifying administrative SSH access and preparing directories..."
ssh_pi "sudo -u mcp-gateway mkdir -p '${REMOTE_TARGET_DIR}/src/mcp_gateway' '${REMOTE_TARGET_DIR}/config' '${REMOTE_TARGET_DIR}/tests' '${REMOTE_TARGET_DIR}/scripts' '${REMOTE_TARGET_DIR}/bin' '${REMOTE_TARGET_DIR}/docs' '/home/mcp-gateway/.local/share/mcp-gateway' '/home/mcp-gateway/.config/mcp-gateway' && sudo chmod 700 '/home/mcp-gateway/.local/share/mcp-gateway' '/home/mcp-gateway/.config/mcp-gateway'"

REMOTE_BIN_SHA="$(ssh_pi "sha256sum '${REMOTE_TARGET_DIR}/bin/mcp-gateway-adapter' 2>/dev/null | cut -d' ' -f1" || true)"
LOCAL_MCP_UNIT_SHA="$(sha256sum "${PROJECT_ROOT}/config/systemd/mcp-gateway-mcp.service" | awk '{print $1}')"
REMOTE_MCP_UNIT_SHA="$(ssh_pi "sha256sum /etc/systemd/system/mcp-gateway-mcp.service 2>/dev/null | cut -d' ' -f1" || true)"
MCP_RESTART_REQUIRED=0
if [ "${LOCAL_BIN_SHA}" != "${REMOTE_BIN_SHA}" ] || [ "${LOCAL_MCP_UNIT_SHA}" != "${REMOTE_MCP_UNIT_SHA}" ]; then
    MCP_RESTART_REQUIRED=1
fi

echo "3. Transferring source, tests, configuration and documentation..."
tar -C "${PROJECT_ROOT}" --exclude='*/__pycache__' --exclude='*.pyc' -czf - \
    src config tests scripts docs bin \
    README.md CHANGELOG.md AGENTS.md CONTRIBUTING.md compatibility.json manifest.json install.sh SHA256SUMS | \
    ssh_pi "sudo -u mcp-gateway tar -xzf - -C '${REMOTE_TARGET_DIR}' && sudo chown -R mcp-gateway:mcp-gateway '${REMOTE_TARGET_DIR}' && sudo chmod -R u+rwX,go+rX '${REMOTE_TARGET_DIR}' && sudo chmod 755 '${REMOTE_TARGET_DIR}/bin/mcp-gateway' '${REMOTE_TARGET_DIR}/bin/mcp-gateway-client-stdio' '${REMOTE_TARGET_DIR}/install.sh'"

echo "4. Uploading candidate adapter for validation on the real ARMv6 host..."
scp_pi "${ADAPTER_STAGE}" "${PI_USER}@${PI_HOST}:/tmp/mcp-gateway-adapter.candidate"
ssh_pi "chmod 755 /tmp/mcp-gateway-adapter.candidate; HELP=\$(/tmp/mcp-gateway-adapter.candidate -help 2>&1 || true); printf '%s\n' \"\$HELP\" | grep -q -- '-auth-token-file'; printf '%s\n' \"\$HELP\" | grep -q -- '-client-id'"

if [ "${LOCAL_BIN_SHA}" != "${REMOTE_BIN_SHA}" ]; then
    echo "5. Installing validated adapter (binary changed)..."
    ssh_pi "STAMP=\$(date +%Y%m%d_%H%M%S); if [ -f '${REMOTE_TARGET_DIR}/bin/mcp-gateway-adapter' ]; then sudo cp '${REMOTE_TARGET_DIR}/bin/mcp-gateway-adapter' '${REMOTE_TARGET_DIR}/bin/mcp-gateway-adapter.predeploy-'\"\$STAMP\"; fi; sudo install -o mcp-gateway -g mcp-gateway -m 0755 /tmp/mcp-gateway-adapter.candidate '${REMOTE_TARGET_DIR}/bin/mcp-gateway-adapter'; rm -f /tmp/mcp-gateway-adapter.candidate"
else
    echo "5. Adapter already matches current source; keeping running binary."
    ssh_pi "rm -f /tmp/mcp-gateway-adapter.candidate"
fi

echo "6. Installing systemd units and restarting Admin Console..."
ssh_pi "sudo cp '${REMOTE_TARGET_DIR}/config/systemd/mcp-gateway-admin.service' /etc/systemd/system/mcp-gateway-admin.service; sudo cp '${REMOTE_TARGET_DIR}/config/systemd/mcp-gateway-mcp.service' /etc/systemd/system/mcp-gateway-mcp.service; sudo systemctl daemon-reload; sudo systemctl enable mcp-gateway-admin mcp-gateway-mcp >/dev/null; sudo systemctl restart mcp-gateway-admin; for i in \$(seq 1 30); do curl -fsS -o /dev/null http://${PI_HOST}/login && break; [ \"\$i\" -eq 30 ] && exit 1; sleep 1; done"

if [ "${MCP_RESTART_REQUIRED}" -eq 1 ]; then
    echo "7. MCP adapter/unit changed: restarting MCP first, then Secure MCP Tunnel..."
    ssh_pi "set -e; sudo systemctl stop mcp-gateway-tunnel 2>/dev/null || true; sudo systemctl reset-failed mcp-gateway-mcp mcp-gateway-tunnel; sudo systemctl restart mcp-gateway-mcp; for i in \$(seq 1 30); do systemctl is-active --quiet mcp-gateway-mcp && curl -fsS http://127.0.0.1:8090/ready >/dev/null && break; [ \"\$i\" -eq 30 ] && exit 1; sleep 1; done; sudo systemctl start mcp-gateway-tunnel; for i in \$(seq 1 60); do systemctl is-active --quiet mcp-gateway-tunnel && break; [ \"\$i\" -eq 60 ] && exit 1; sleep 1; done"
else
    echo "7. MCP adapter/unit unchanged; preserving the active tunnel session."
fi

echo "8. Running remote smoke tests as mcp-gateway..."
if [ "${MCP_DEPLOY_FULL_REMOTE_TESTS:-0}" = "1" ]; then
    ssh_pi "sudo -u mcp-gateway python3 -m unittest discover -s '${REMOTE_TARGET_DIR}/tests' -p 'test_*.py'"
else
    ssh_pi "set -e; sudo -u mcp-gateway python3 -m unittest discover -s '${REMOTE_TARGET_DIR}/tests' -p 'test_web_*.py'; sudo -u mcp-gateway python3 -m unittest discover -s '${REMOTE_TARGET_DIR}/tests' -p 'test_appliance_tools.py'; sudo -u mcp-gateway python3 -m unittest discover -s '${REMOTE_TARGET_DIR}/tests' -p 'test_bridge.py'"
fi

echo "9. Recording deployed Git commit..."
ssh_pi "printf '%s\n' '${DEPLOY_SHA}' | sudo -u mcp-gateway tee '${REMOTE_TARGET_DIR}/.deployed-git-sha' >/dev/null; printf '%s\n' '${DEPLOY_BRANCH}' | sudo -u mcp-gateway tee '${REMOTE_TARGET_DIR}/.deployed-git-branch' >/dev/null"

echo "10. Final live checks..."
ssh_pi "set -e; systemctl is-active --quiet mcp-gateway-admin; systemctl is-active --quiet mcp-gateway-mcp; systemctl is-active --quiet mcp-gateway-tunnel; curl -fsS -o /dev/null http://${PI_HOST}/login; curl -fsS http://127.0.0.1:8090/live >/dev/null; curl -fsS http://127.0.0.1:8090/ready >/dev/null; test \"\$(sha256sum '${REMOTE_TARGET_DIR}/bin/mcp-gateway-adapter' | cut -d' ' -f1)\" = '${LOCAL_BIN_SHA}'"

echo "=== Deployment and verification completed successfully ==="

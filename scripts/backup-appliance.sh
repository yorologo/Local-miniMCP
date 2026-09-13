#!/usr/bin/env bash
# scripts/backup-appliance.sh
# Reproducible Disaster Recovery backup for MCP-Pi Gateway (v1.2.1)
# Creates a consistent, isolated, private snapshot of all stateful data & identities.
#
# Usage:
#   sudo ./scripts/backup-appliance.sh [DESTINATION_DIR]
#
# Principles: KISS + Reuse First + Least Privilege + Zero Secrets in Logs/Git

set -euo pipefail

# 1. Privileges check
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: backup-appliance.sh must be executed as root (e.g. via sudo) to read host keys and service state." >&2
    exit 1
fi

DEST_DIR="${1:-/home/yorologo/backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RELEASE_TAG="v1.2.1"
ARCHIVE_NAME="mcp-pi-${RELEASE_TAG}-${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${DEST_DIR}/${ARCHIVE_NAME}"
SHA_PATH="${ARCHIVE_PATH}.sha256"

echo "=== MCP-Pi Appliance Backup ==="
echo "Timestamp:    ${TIMESTAMP} (UTC)"
echo "Release:      ${RELEASE_TAG}"
echo "Destination:  ${DEST_DIR}"

# 2. Check destination disk space (require at least 50MB free)
mkdir -p "${DEST_DIR}"
chmod 0700 "${DEST_DIR}"
chown yorologo:yorologo "${DEST_DIR}" 2>/dev/null || true

AVAILABLE_KB=$(df -k --output=avail "${DEST_DIR}" | tail -n 1 | tr -dc '0-9')
if [ "${AVAILABLE_KB:-0}" -lt 51200 ]; then
    echo "ERROR: Insufficient disk space at ${DEST_DIR} (available: ${AVAILABLE_KB} KB, required: 51200 KB)." >&2
    exit 1
fi

# 3. Create secure isolated staging directory
STAGING_DIR="$(mktemp -d /tmp/mcp-pi-backup-staging.XXXXXX)"
chmod 0700 "${STAGING_DIR}"
trap 'rm -rf "${STAGING_DIR}"' EXIT

mkdir -p "${STAGING_DIR}/data"
mkdir -p "${STAGING_DIR}/config"
mkdir -p "${STAGING_DIR}/gateway-ssh"
mkdir -p "${STAGING_DIR}/host-ssh"
mkdir -p "${STAGING_DIR}/admin-ssh"
mkdir -p "${STAGING_DIR}/systemd"

# 4. Consistent SQLite snapshot via Python standard library Online Backup API
DB_SRC="/home/mcp-gateway/.local/share/mcp-gateway/gateway.db"
DB_DST="${STAGING_DIR}/data/gateway.db"

if [ -f "${DB_SRC}" ]; then
    echo "Creating consistent SQLite snapshot via Python sqlite3 backup API..."
    python3 -c "
import sqlite3, sys
try:
    src = sqlite3.connect('${DB_SRC}')
    dst = sqlite3.connect('${DB_DST}')
    src.backup(dst)
    dst.close()
    src.close()
    
    # Verify snapshot integrity
    check = sqlite3.connect('${DB_DST}')
    res = check.cursor().execute('PRAGMA integrity_check;').fetchone()[0]
    ver = check.cursor().execute('PRAGMA user_version;').fetchone()[0]
    check.close()
    if res != 'ok':
        print(f'ERROR: snapshot integrity failed: {res}', file=sys.stderr)
        sys.exit(2)
    print(f'SQLite snapshot OK: integrity={res}, user_version={ver}')
except Exception as e:
    print(f'ERROR: SQLite backup failed: {e}', file=sys.stderr)
    sys.exit(1)
"
    chmod 0600 "${DB_DST}"
    chown mcp-gateway:mcp-gateway "${DB_DST}" 2>/dev/null || true
else
    echo "WARNING: ${DB_SRC} not found."
fi

# 5. Collect config and secrets
CONF_SRC="/home/mcp-gateway/.config/mcp-gateway"
if [ -d "${CONF_SRC}" ]; then
    for f in admin-secret tunnel.env tunnel-mcp.token; do
        if [ -f "${CONF_SRC}/${f}" ]; then
            cp -p "${CONF_SRC}/${f}" "${STAGING_DIR}/config/"
            chmod 0600 "${STAGING_DIR}/config/${f}"
        fi
    done
fi

# 6. Collect Gateway SSH identity & known_hosts
SSH_SRC="/home/mcp-gateway/.ssh"
if [ -d "${SSH_SRC}" ]; then
    for f in mcp_gateway_ed25519 mcp_gateway_ed25519.pub known_hosts config; do
        if [ -f "${SSH_SRC}/${f}" ]; then
            cp -p "${SSH_SRC}/${f}" "${STAGING_DIR}/gateway-ssh/"
        fi
    done
fi

# 7. Collect Host SSH keys
if [ -d "/etc/ssh" ]; then
    for f in /etc/ssh/ssh_host_*; do
        if [ -f "${f}" ]; then
            cp -p "${f}" "${STAGING_DIR}/host-ssh/"
        fi
    done
fi

# 8. Collect Admin SSH authorized_keys
if [ -f "/home/yorologo/.ssh/authorized_keys" ]; then
    cp -p "/home/yorologo/.ssh/authorized_keys" "${STAGING_DIR}/admin-ssh/"
    chmod 0600 "${STAGING_DIR}/admin-ssh/authorized_keys"
fi

# 9. Collect systemd units for exact reference
for u in /etc/systemd/system/mcp-gateway*.service /etc/systemd/system/mcp-gateway*.timer; do
    if [ -f "${u}" ]; then
        cp -p "${u}" "${STAGING_DIR}/systemd/"
    fi
done

# 10. Generate non-secret manifest (metadata, fingerprints, file inventory, NO SECRET DATA)
python3 -c "
import os, sys, json, hashlib, subprocess, stat, pwd, grp

staging = '${STAGING_DIR}'
release = '${RELEASE_TAG}'
timestamp = '${TIMESTAMP}'

# Fingerprints
host_fp = 'UNKNOWN'
if os.path.exists(os.path.join(staging, 'host-ssh/ssh_host_ed25519_key.pub')):
    res = subprocess.run(['ssh-keygen', '-lf', os.path.join(staging, 'host-ssh/ssh_host_ed25519_key.pub')], capture_output=True, text=True)
    if res.returncode == 0:
        host_fp = res.stdout.strip()

client_fp = 'UNKNOWN'
if os.path.exists(os.path.join(staging, 'gateway-ssh/mcp_gateway_ed25519.pub')):
    res = subprocess.run(['ssh-keygen', '-lf', os.path.join(staging, 'gateway-ssh/mcp_gateway_ed25519.pub')], capture_output=True, text=True)
    if res.returncode == 0:
        client_fp = res.stdout.strip()

target_pins = []
if os.path.exists(os.path.join(staging, 'gateway-ssh/known_hosts')):
    res = subprocess.run(['ssh-keygen', '-lf', os.path.join(staging, 'gateway-ssh/known_hosts')], capture_output=True, text=True)
    if res.returncode == 0:
        target_pins = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]

# DB info
db_info = {}
db_path = os.path.join(staging, 'data/gateway.db')
if os.path.exists(db_path):
    import sqlite3
    c = sqlite3.connect(db_path)
    cur = c.cursor()
    db_info['integrity'] = cur.execute('PRAGMA integrity_check;').fetchone()[0]
    db_info['user_version'] = cur.execute('PRAGMA user_version;').fetchone()[0]
    tables = [r[0] for r in cur.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;\").fetchall()]
    db_info['tables'] = {}
    for t in tables:
        db_info['tables'][t] = cur.execute(f'SELECT COUNT(*) FROM {t};').fetchone()[0]
    c.close()

# Inventory of files in staging
files = []
for root, dirs, filenames in os.walk(staging):
    for f in filenames:
        if f == 'manifest.json':
            continue
        full_path = os.path.join(root, f)
        rel_path = os.path.relpath(full_path, staging)
        st = os.stat(full_path)
        
        # SHA256 of the backup copy
        h = hashlib.sha256()
        with open(full_path, 'rb') as fp:
            while chunk := fp.read(65536):
                h.update(chunk)
        
        try:
            owner = pwd.getpwuid(st.st_uid).pw_name
        except:
            owner = str(st.st_uid)
        try:
            group = grp.getgrgid(st.st_gid).gr_name
        except:
            group = str(st.st_gid)
            
        files.append({
            'path': rel_path,
            'size': st.st_size,
            'mode': oct(st.st_mode & 0o777),
            'owner': owner,
            'group': group,
            'sha256': h.hexdigest()
        })

manifest = {
    'appliance': 'MCP-Pi Gateway',
    'release': release,
    'backup_timestamp_utc': timestamp,
    'host_fingerprint': host_fp,
    'client_fingerprint': client_fp,
    'target_pinned_keys': target_pins,
    'database': db_info,
    'total_files': len(files),
    'files': sorted(files, key=lambda x: x['path'])
}

with open(os.path.join(staging, 'manifest.json'), 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2)
print('Manifest created successfully.')
"

# 11. Create archive
echo "Packaging private backup archive..."
tar -czf "${ARCHIVE_PATH}" -C "${STAGING_DIR}" .

# 12. Strict permissions on archive (mode 0600)
chmod 0600 "${ARCHIVE_PATH}"
chown yorologo:yorologo "${ARCHIVE_PATH}" 2>/dev/null || true

# 13. SHA256 checksum
(cd "${DEST_DIR}" && sha256sum "${ARCHIVE_NAME}" > "${ARCHIVE_NAME}.sha256")
chmod 0644 "${SHA_PATH}"
chown yorologo:yorologo "${SHA_PATH}" 2>/dev/null || true

# Extract manifest copy for non-secret verification
tar -xzf "${ARCHIVE_PATH}" ./manifest.json -O > "${DEST_DIR}/manifest-${RELEASE_TAG}-${TIMESTAMP}.json"
chmod 0644 "${DEST_DIR}/manifest-${RELEASE_TAG}-${TIMESTAMP}.json"
chown yorologo:yorologo "${DEST_DIR}/manifest-${RELEASE_TAG}-${TIMESTAMP}.json" 2>/dev/null || true

ARCHIVE_SIZE=$(stat -c%s "${ARCHIVE_PATH}")
ARCHIVE_SHA256=$(cut -d' ' -f1 "${SHA_PATH}")

echo "=== Backup Complete ==="
echo "Archive:  ${ARCHIVE_PATH}"
echo "Size:     ${ARCHIVE_SIZE} bytes"
echo "SHA256:   ${ARCHIVE_SHA256}"
echo "Manifest: ${DEST_DIR}/manifest-${RELEASE_TAG}-${TIMESTAMP}.json"

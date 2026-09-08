"""Lifecycle management for MCP Gateway: setup, backup, restore, update, rollback, uninstall."""

import hashlib
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from . import compatibility
from .doctor import run_doctor


def get_paths() -> Dict[str, str]:
    home = os.path.expanduser("~")
    base_install = os.environ.get("MCP_GATEWAY_HOME", "/home/mcp-gateway")
    return {
        "home": base_install,
        "releases": os.path.join(base_install, "releases"),
        "current": os.path.join(base_install, "current"),
        "previous": os.path.join(base_install, "previous"),
        "data": os.path.join(base_install, ".local", "share", "mcp-gateway"),
        "config": os.path.join(base_install, ".config", "mcp-gateway"),
        "db": os.environ.get("MCP_GATEWAY_DB", os.path.join(base_install, ".local", "share", "mcp-gateway", "gateway.db")),
        "backups": os.path.join(base_install, ".local", "share", "mcp-gateway", "backups"),
    }


def create_manifest(version: Optional[str] = None, output_path: Optional[str] = None) -> Dict[str, Any]:
    compat = compatibility.get_compatibility()
    manifest = {
        "version": version or compat.get("gateway_version", "0.6.0"),
        "architecture": "armv6l",
        "architectures": ["armv6l", "aarch64", "x86_64"],
        "core_api": compat.get("core_api_version", 1),
        "bridge_api": compat.get("bridge_api_version", 1),
        "tool_catalog": compat.get("tool_catalog_version", 2),
        "registry_schema_range": f">={compat.get('registry_schema_version', 1)}",
        "mcp_sdk": compat.get("mcp", {}).get("sdk", "go-sdk"),
        "mcp_sdk_version": compat.get("mcp", {}).get("version", "1.7.0"),
        "mcp_protocol": compat.get("mcp", {}).get("protocol", "2026-07-28"),
        "minimum_python": "3.9",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    return manifest


def verify_manifest(manifest_path: str) -> Tuple[bool, List[str]]:
    if not os.path.isfile(manifest_path):
        return False, [f"Manifest file not found: {manifest_path}"]

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, [f"Failed to parse manifest: {e}"]

    errors = []
    # Check architecture
    arch = platform.machine()
    allowed_archs = data.get("architectures")
    if allowed_archs:
        if arch not in allowed_archs and "all" not in allowed_archs:
            errors.append(f"Architecture mismatch: package supports {allowed_archs}, system is '{arch}'")
    else:
        m_arch = data.get("architecture")
        if m_arch and m_arch != "all" and m_arch != arch:
            errors.append(f"Architecture mismatch: package is '{m_arch}', system is '{arch}'")

    # Check contract compatibility
    ok, comp_errors = compatibility.verify_compatibility(data)
    if not ok:
        errors.extend(comp_errors)

    return len(errors) == 0, errors


def backup_database(dest_path: Optional[str] = None) -> str:
    paths = get_paths()
    src_db = paths["db"]
    if not os.path.isfile(src_db):
        raise FileNotFoundError(f"Database not found at {src_db}")

    if not dest_path:
        os.makedirs(paths["backups"], exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        dest_path = os.path.join(paths["backups"], f"gateway_backup_{ts}.db")

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    src_conn = sqlite3.connect(src_db)
    dst_conn = sqlite3.connect(dest_path)
    with dst_conn:
        src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()
    return dest_path


def restore_database(backup_path: str) -> bool:
    if not os.path.isfile(backup_path):
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    # Validate backup integrity
    conn = sqlite3.connect(backup_path)
    cur = conn.cursor()
    cur.execute("PRAGMA integrity_check;")
    row = cur.fetchone()
    if not row or row[0] != "ok":
        conn.close()
        raise ValueError(f"Backup file integrity check failed: {row}")

    cur.execute("PRAGMA user_version;")
    ver = cur.fetchone()[0]
    expected_ver = compatibility.get_registry_schema_version()
    if ver < expected_ver:
        conn.close()
        raise ValueError(f"Backup schema version {ver} is incompatible with expected {expected_ver}")
    conn.close()

    paths = get_paths()
    target_db = paths["db"]
    os.makedirs(os.path.dirname(target_db), exist_ok=True)

    # Perform online restore
    src_conn = sqlite3.connect(backup_path)
    dst_conn = sqlite3.connect(target_db)
    with dst_conn:
        src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()
    return True


def rollback_release() -> Tuple[bool, str]:
    paths = get_paths()
    previous = paths["previous"]
    current = paths["current"]

    if not os.path.islink(previous) and not os.path.isdir(previous):
        return False, "No previous release symlink found for rollback"

    prev_target = os.path.realpath(previous)
    if not os.path.isdir(prev_target):
        return False, f"Previous release target {prev_target} does not exist"

    # Verify compatibility of previous release
    manifest_file = os.path.join(prev_target, "manifest.json")
    if os.path.isfile(manifest_file):
        ok, errs = verify_manifest(manifest_file)
        if not ok:
            return False, f"Cannot rollback to incompatible release: {errs}"

    # Swap symlinks
    temp_link = current + ".rollback_tmp"
    if os.path.lexists(temp_link):
        os.remove(temp_link)
    os.symlink(prev_target, temp_link)
    os.replace(temp_link, current)

    # Restart services
    subprocess.run(["systemctl", "restart", "mcp-gateway-admin", "mcp-gateway-mcp"], check=False)
    return True, f"Successfully rolled back current release to {prev_target}"


def uninstall(purge: bool = False) -> List[str]:
    actions = []
    # 1. Stop and disable services
    for svc in ("mcp-gateway-mcp", "mcp-gateway-admin"):
        try:
            subprocess.run(["systemctl", "stop", svc], check=False)
            subprocess.run(["systemctl", "disable", svc], check=False)
            actions.append(f"Stopped and disabled service {svc}")
        except Exception:
            pass

    # 2. Remove systemd unit files
    for unit in ("/etc/systemd/system/mcp-gateway-mcp.service", "/etc/systemd/system/mcp-gateway-admin.service"):
        if os.path.isfile(unit):
            try:
                os.remove(unit)
                actions.append(f"Removed systemd unit {unit}")
            except Exception:
                pass
    subprocess.run(["systemctl", "daemon-reload"], check=False)

    # 3. Remove CLI symlink if present
    for cli in ("/usr/local/bin/mcp-gateway", "/usr/bin/mcp-gateway"):
        if os.path.islink(cli) or os.path.isfile(cli):
            try:
                os.remove(cli)
                actions.append(f"Removed CLI executable {cli}")
            except Exception:
                pass

    paths = get_paths()
    if purge:
        if os.path.isdir(paths["data"]):
            shutil.rmtree(paths["data"], ignore_errors=True)
            actions.append(f"Purged data directory {paths['data']}")
        if os.path.isdir(paths["config"]):
            shutil.rmtree(paths["config"], ignore_errors=True)
            actions.append(f"Purged config directory {paths['config']}")
    else:
        actions.append(f"Preserved data directory {paths['data']} and config {paths['config']}")

    return actions

"""Unified User CLI for MCP Gateway."""

import argparse
import json
import os
import sys
from typing import List, Optional

from . import compatibility
from .doctor import run_doctor, run_repair
from .lifecycle import backup_database, restore_database, rollback_release, update_release, check_candidate, uninstall, get_paths
from .registry import get_registry
from .tools import GatewayTools


def cmd_status() -> int:
    try:
        reg = get_registry()
        tools = GatewayTools(registry=reg)
        h = tools.health()
        res = h.get("result", {})
        print("==================================================")
        print(f"MCP Gateway: {res.get('gateway_version')} (Architecture: {res.get('architecture')})")
        print(f"Status:      {'ONLINE' if h.get('ok') else 'OFFLINE'}")
        print(f"Writes:      {'ENABLED' if res.get('writes_enabled') else 'DISABLED'}")
        print(f"Targets:     {res.get('target_count', 0)} configured")
        print("==================================================")
        return 0 if h.get("ok") else 1
    except Exception as e:
        print(f"[ERROR] Could not query gateway status: {e}", file=sys.stderr)
        return 1


def cmd_doctor(verbose: bool = False, check_targets: bool = False) -> int:
    overall, checks = run_doctor(verbose=verbose, check_targets=check_targets)
    print("==================================================")
    print("=== MCP GATEWAY DOCTOR: SYSTEM HEALTH CHECK    ===")
    print("==================================================")
    for c in checks:
        if c.passed:
            status_tag = "\033[92m[PASS]\033[0m"
        elif c.severity == "warning":
            status_tag = "\033[93m[WARN]\033[0m"
        else:
            status_tag = "\033[91m[FAIL]\033[0m"
        print(f"{status_tag} {c.name:28} : {c.message}")
    print("==================================================")
    color = "\033[92m" if overall == "HEALTHY" else ("\033[93m" if overall == "DEGRADED" else "\033[91m")
    print(f"OVERALL STATUS: {color}{overall}\033[0m")
    print("==================================================")
    return 0 if overall in ("HEALTHY", "DEGRADED") else 1


def cmd_repair() -> int:
    print("Executing safe repair actions...")
    repairs = run_repair()
    if not repairs:
        print("No repairs needed or executed.")
    else:
        for r in repairs:
            print(f"- {r}")
    print("\nRe-evaluating system health:")
    return cmd_doctor(verbose=False)


def cmd_backup(dest_path: Optional[str] = None) -> int:
    try:
        path = backup_database(dest_path)
        print(f"[OK] Database backed up successfully to: {path}")
        return 0
    except Exception as e:
        print(f"[ERROR] Backup failed: {e}", file=sys.stderr)
        return 1


def cmd_maintenance() -> int:
    print("==================================================")
    print("=== MCP GATEWAY APPLIANCE SAFE MAINTENANCE     ===")
    print("==================================================")
    try:
        reg = get_registry()
        tools = GatewayTools(registry=reg, client_id="local")
        res = tools.gateway_maintenance()
        if not res.get("ok"):
            print(f"[ERROR] Maintenance failed: {res.get('error')}", file=sys.stderr)
            return 1
        r = res.get("result", {})
        print(f"[OK] Database Backup      : {r.get('backup_created')} ({r.get('backup_size_bytes')} bytes)")
        print(f"[OK] Pruned Old Backups   : {r.get('pruned_backups_count')} backup(s) pruned (kept latest 5)")
        print(f"[OK] SQLite Integrity     : {r.get('database_integrity')}")
        print(f"[OK] Doctor Overall       : {r.get('doctor_status')}")
        print(f"[OK] Security Updates     : {r.get('security_updates', 'unknown')}")
        res_info = r.get("resources", {})
        print(f"[OK] Rootfs Free Space    : {res_info.get('disk_free_gb')} GB")
        print(f"[OK] Available Memory     : {res_info.get('memory_available_mb')} MB")
        print("==================================================")
        print("STATUS: MAINTENANCE COMPLETED SUCCESSFULLY")
        print("==================================================")
        return 0
    except Exception as e:
        print(f"[ERROR] Maintenance encountered exception: {e}", file=sys.stderr)
        return 1


def cmd_restore(backup_path: str) -> int:
    try:
        restore_database(backup_path)
        print(f"[OK] Database restored successfully from: {backup_path}")
        return cmd_doctor(verbose=False)
    except Exception as e:
        print(f"[ERROR] Restore failed: {e}", file=sys.stderr)
        return 1


def cmd_rollback() -> int:
    ok, msg = rollback_release()
    if ok:
        print(f"[OK] {msg}")
        return cmd_doctor(verbose=False)
    else:
        print(f"[ERROR] Rollback failed: {msg}", file=sys.stderr)
        return 1


def cmd_update(candidate_path: Optional[str] = None, check_only: bool = False) -> int:
    print("==================================================")
    print("=== MCP Gateway Release Update                 ===")
    print("==================================================")
    paths = get_paths()
    if not candidate_path:
        candidate_path = paths.get("root", ".")

    if check_only:
        print(f"Checking candidate release at: {candidate_path}")
        ok, errs, meta = check_candidate(candidate_path)
        if ok:
            print(f"[PASS] Candidate manifest valid: v{meta.get('version', 'unknown')}")
            archs = meta.get("compatibility", {}).get("architectures", [])
            print(f"[PASS] Architecture compatibility: {archs}")
            print(f"[PASS] Checksums verified: SHA256SUMS intact")
            print(f"[OK] Candidate release passed pre-update validation.")
            return 0
        else:
            print(f"[FAIL] Candidate release check failed:")
            for e in errs:
                print(f"  - {e}")
            return 1

    ok, msg = update_release(candidate_path)
    if ok:
        print(f"[OK] {msg}")
        return cmd_doctor(verbose=False)
    else:
        print(f"[ERROR] Update failed: {msg}", file=sys.stderr)
        return 1


def cmd_setup() -> int:
    print("==================================================")
    print("=== MCP Gateway Quick Setup                    ===")
    print("==================================================")
    print(f"Contract: Gateway v{compatibility.get_gateway_version()}, MCP Protocol 2026-07-28")
    print("Running initial doctor diagnostics...")
    cmd_doctor(verbose=False)
    print("\nSetup completed. Use 'mcp-gateway --help' for available management commands.")
    return 0


def cmd_uninstall(purge: bool = False, confirm: bool = False) -> int:
    if purge and not confirm:
        print("[WARNING] Purge will delete all gateway data, backups, and configurations!")
        resp = input("Type 'PURGE' to confirm: ")
        if resp.strip() != "PURGE":
            print("Purge cancelled.")
            return 1
    actions = uninstall(purge=purge)
    for a in actions:
        print(f"- {a}")
    print("MCP Gateway uninstallation complete.")
    return 0


def main(args_list: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="mcp-gateway", description="MCP Gateway Unified Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show gateway status summary")
    subparsers.add_parser("setup", help="Run initial gateway setup wizard")

    doc_p = subparsers.add_parser("doctor", help="Run comprehensive system diagnostics")
    doc_p.add_argument("--verbose", action="store_true", help="Include verbose diagnostic details")
    doc_p.add_argument("--check-targets", action="store_true", help="Probe remote target connectivity")

    subparsers.add_parser("repair", help="Perform safe, non-destructive permissions and service repairs")

    bak_p = subparsers.add_parser("backup", help="Create an online database backup")
    bak_p.add_argument("path", nargs="?", default=None, help="Destination backup file path")

    res_p = subparsers.add_parser("restore", help="Restore database from an existing backup file")
    res_p.add_argument("backup_file", help="Path to database backup file")

    up_p = subparsers.add_parser("update", help="Update MCP Gateway release from candidate directory or package")
    up_p.add_argument("candidate_path", nargs="?", default=None, help="Path to candidate release directory or tarball")
    up_p.add_argument("--check", action="store_true", help="Validate candidate release without applying")

    subparsers.add_parser("rollback", help="Roll back current release to previous version")

    subparsers.add_parser("maintenance", help="Run safe automated maintenance (backup, rotation, integrity, doctor)")

    un_p = subparsers.add_parser("uninstall", help="Uninstall MCP Gateway services and binaries")
    un_p.add_argument("--purge", action="store_true", help="Purge all data, databases, and configuration")
    un_p.add_argument("--confirm", action="store_true", help="Skip interactive purge confirmation")

    parsed = parser.parse_args(args_list)

    if parsed.command == "status":
        return cmd_status()
    elif parsed.command == "setup":
        return cmd_setup()
    elif parsed.command == "doctor":
        return cmd_doctor(verbose=parsed.verbose, check_targets=parsed.check_targets)
    elif parsed.command == "repair":
        return cmd_repair()
    elif parsed.command == "backup":
        return cmd_backup(parsed.path)
    elif parsed.command == "maintenance":
        return cmd_maintenance()
    elif parsed.command == "restore":
        return cmd_restore(parsed.backup_file)
    elif parsed.command == "update":
        return cmd_update(parsed.candidate_path, check_only=parsed.check)
    elif parsed.command == "rollback":
        return cmd_rollback()
    elif parsed.command == "uninstall":
        return cmd_uninstall(purge=parsed.purge, confirm=parsed.confirm)

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Unified User CLI for MCP Gateway."""

import argparse
import json
import os
import socket
import sys
from typing import List, Optional

from . import compatibility
from .doctor import run_doctor, run_repair
from .lifecycle import backup_database, restore_database, check_candidate, uninstall
from .registry import get_registry, get_default_db_path
from .admin_cli import set_password_cmd
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
    print("Rollback is an administrative filesystem operation and must run as root.")
    print("Run: sudo /home/mcp-gateway/mcp-gateway/install.sh --rollback")
    return 2


def cmd_update(candidate_path: Optional[str] = None, check_only: bool = False) -> int:
    print("==================================================")
    print("=== MCP Gateway Release Update                 ===")
    print("==================================================")
    if check_only:
        if not candidate_path:
            print("[ERROR] --check requires a candidate release directory or tarball", file=sys.stderr)
            return 2
        print(f"Checking candidate release at: {candidate_path}")
        ok, errs, meta = check_candidate(candidate_path)
        if ok:
            print(f"[PASS] Candidate manifest valid: v{meta.get('version', 'unknown')}")
            archs = meta.get("architectures", meta.get("compatibility", {}).get("architectures", []))
            print(f"[PASS] Architecture compatibility: {archs}")
            print("[PASS] Checksums verified when SHA256SUMS is present")
            return 0
        print("[FAIL] Candidate release validation failed:")
        for error in errs:
            print(f"  - {error}")
        return 1

    print("Application updates are root-level operations in the current appliance layout.")
    print("Extract the new official release bundle and run: sudo ./install.sh")
    print("Maintainers promoting an exact Git commit use the resumable runner: scripts/run-resumable.sh start --expect-marker DEPLOYMENT_VERIFIED <job> -- scripts/deploy-pi.sh <exact-sha>")
    return 2


def _setup_admin_url() -> str:
    host = socket.gethostname().strip() or "localhost"
    return f"http://{host}/"


def cmd_setup(admin_user: str = "admin", skip_password: bool = False, password_stdin: bool = False) -> int:
    print("==================================================")
    print("=== MCP Gateway Initial Setup                  ===")
    print("==================================================")
    print(f"Contract: Gateway v{compatibility.get_gateway_version()}, MCP Protocol 2026-07-28")

    registry = get_registry()
    existing = registry.get_admin_user(admin_user)
    if not skip_password:
        should_set = password_stdin or existing is None
        if should_set:
            if password_stdin or sys.stdin.isatty():
                rc = set_password_cmd(admin_user, get_default_db_path())
                if rc != 0:
                    return rc
            else:
                print("[ACTION REQUIRED] No Admin password is configured and stdin is not interactive.", file=sys.stderr)
                print(f"Run interactively: mcp-gateway setup --admin-user {admin_user}", file=sys.stderr)
                print("Or pipe a password once with: mcp-gateway setup --password-stdin", file=sys.stderr)
                return 2
        else:
            print(f"[OK] Admin user '{admin_user}' is already configured; password left unchanged.")

    print("Running Doctor...")
    rc = cmd_doctor(verbose=False)
    if rc != 0:
        return rc

    print("\nSetup baseline complete.")
    print(f"Admin Console: {_setup_admin_url()}")
    print("Next: sign in to Admin Console and add the first Target, Project, client and grant.")
    print("Security defaults on a fresh Registry keep structured writes and trusted Target shell disabled until explicitly enabled.")
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
    setup_p = subparsers.add_parser("setup", help="Configure initial Admin access and run Doctor")
    setup_p.add_argument("--admin-user", default="admin", help="Admin username to configure (default: admin)")
    setup_p.add_argument("--skip-password", action="store_true", help="Skip Admin password bootstrap")
    setup_p.add_argument("--password-stdin", action="store_true", help="Read the Admin password once from stdin")

    doc_p = subparsers.add_parser("doctor", help="Run comprehensive system diagnostics")
    doc_p.add_argument("--verbose", action="store_true", help="Include verbose diagnostic details")
    doc_p.add_argument("--check-targets", action="store_true", help="Probe remote target connectivity")

    subparsers.add_parser("repair", help="Perform safe, non-destructive permissions and service repairs")

    bak_p = subparsers.add_parser("backup", help="Create an online database backup")
    bak_p.add_argument("path", nargs="?", default=None, help="Destination backup file path")

    res_p = subparsers.add_parser("restore", help="Restore database from an existing backup file")
    res_p.add_argument("backup_file", help="Path to database backup file")

    up_p = subparsers.add_parser("update", help="Validate a release candidate or show the supported root-level update path")
    up_p.add_argument("candidate_path", nargs="?", default=None, help="Path to candidate release directory or tarball")
    up_p.add_argument("--check", action="store_true", help="Validate candidate release without applying")

    subparsers.add_parser("rollback", help="Show the supported root-level installer rollback command")

    subparsers.add_parser("maintenance", help="Run safe automated maintenance (backup, rotation, integrity, doctor)")

    un_p = subparsers.add_parser("uninstall", help="Uninstall MCP Gateway services and binaries")
    un_p.add_argument("--purge", action="store_true", help="Purge all data, databases, and configuration")
    un_p.add_argument("--confirm", action="store_true", help="Skip interactive purge confirmation")

    parsed = parser.parse_args(args_list)

    if parsed.command == "status":
        return cmd_status()
    elif parsed.command == "setup":
        return cmd_setup(parsed.admin_user, parsed.skip_password, parsed.password_stdin)
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

#!/usr/bin/env python3
"""Live integration, disable, kill switch, and resource verification on MCP-Pi."""

import json
import os
import sys
import time

# Ensure src is on sys.path
sys.path.insert(0, "/home/mcp-gateway/mcp-gateway/src")

from mcp_gateway.registry import SQLiteRegistry
from mcp_gateway.tools import GatewayTools
from mcp_gateway.ssh_transport import SSHTransport


def run_verification():
    db_path = "/home/mcp-gateway/.local/share/mcp-gateway/gateway.db"
    print(f"Connecting to registry database: {db_path}")
    reg = SQLiteRegistry(db_path)
    tools = GatewayTools(registry=reg, transport=SSHTransport())

    print("\n=== TEST 1: HEALTH AND TARGET STATUS VIA SQLITE REGISTRY ===")
    health = tools.health()
    print("Health:", json.dumps(health, indent=2))
    assert health["ok"] is True, f"Health check failed: {health}"

    targets = tools.list_targets()
    print("Targets:", json.dumps(targets, indent=2))
    assert targets["ok"] is True, f"List targets failed: {targets}"

    status = tools.target_status("termux-main")
    print("Target status (termux-main):", json.dumps(status, indent=2))
    assert status["ok"] is True, f"Target status failed: {status}"

    print("\n=== TEST 2: TARGET DISABLE / ENABLE CYCLE ===")
    print("Disabling target 'termux-main' in SQLite registry...")
    reg.update_target("termux-main", {"enabled": False})
    
    status_disabled = tools.target_status("termux-main")
    print("Target status when disabled:", json.dumps(status_disabled, indent=2))
    assert status_disabled["ok"] is False, "Expected failure on disabled target"
    assert status_disabled["error"]["code"] == "TARGET_DISABLED", f"Expected TARGET_DISABLED, got {status_disabled}"

    print("Re-enabling target 'termux-main' in SQLite registry...")
    reg.update_target("termux-main", {"enabled": True})
    
    status_reenabled = tools.target_status("termux-main")
    print("Target status after re-enabling:", json.dumps(status_reenabled, indent=2))
    assert status_reenabled["ok"] is True, f"Expected success after re-enable, got {status_reenabled}"

    print("\n=== TEST 3: GLOBAL KILL SWITCH CYCLE ===")
    print("Activating Kill Switch: setting gateway_enabled = 'false'...")
    reg.set_setting("gateway_enabled", "false")

    health_disabled = tools.health()
    print("Health during kill switch:", json.dumps(health_disabled, indent=2))
    assert health_disabled["ok"] is True
    assert health_disabled["result"]["gateway_status"] == "disabled"
    assert health_disabled["result"]["gateway_enabled"] is False

    status_killed = tools.target_status("termux-main")
    print("Target status during kill switch:", json.dumps(status_killed, indent=2))
    assert status_killed["ok"] is False, "Expected tool denial during kill switch"
    assert status_killed["error"]["code"] == "GATEWAY_DISABLED", f"Expected GATEWAY_DISABLED, got {status_killed}"

    ls_killed = tools.list_directory("termux-main", "MCP_Local", ".")
    print("List directory during kill switch:", json.dumps(ls_killed, indent=2))
    assert ls_killed["ok"] is False
    assert ls_killed["error"]["code"] == "GATEWAY_DISABLED"

    print("Deactivating Kill Switch: setting gateway_enabled = 'true'...")
    reg.set_setting("gateway_enabled", "true")

    health_active = tools.health()
    print("Health after deactivation:", json.dumps(health_active, indent=2))
    assert health_active["result"]["gateway_status"] == "ok"
    assert health_active["result"]["gateway_enabled"] is True

    status_active = tools.target_status("termux-main")
    print("Target status after deactivation:", json.dumps(status_active, indent=2))
    assert status_active["ok"] is True

    print("\n=== ALL FUNCTIONAL CONTROL TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    run_verification()

#!/usr/bin/env python3
"""Comprehensive Phase 6A Verification Suite.

Validates:
1. Gemini CLI Client (gemini-main):
   - Authenticates via dedicated Ed25519 SSH key
   - Forced command binds client_id to 'gemini-main'
   - tools/list dynamically filtered to 8 tools (write_file excluded)
   - tools/call health succeeds
   - tools/call write_file is rejected
2. Claude Desktop Client (claude-desktop):
   - Authenticates via dedicated Ed25519 SSH key
   - Forced command binds client_id to 'claude-desktop'
   - tools/list dynamically filtered to read-only tools (write_file and run_task excluded)
   - tools/call health succeeds
   - tools/call write_file is rejected
3. Dynamic Grant Management:
   - Add write grant to gemini-main -> write_file appears in tools/list
   - Revoke write grant -> write_file disappears from tools/list
4. Client Lifecycle & Emergency Disablement:
   - Disable gemini-main -> requests immediately rejected
   - Re-enable gemini-main -> requests succeed again
"""

import json
import os
import sys
import time
import paramiko

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.pi_ssh import run_remote

HOST = os.environ.get("MCP_PI_HOST", "192.168.68.85")
USER = "mcp-gateway"


def create_client_session(key_name, client_label):
    key_path = os.path.expanduser(f"~/.ssh/{key_name}")
    for attempt in range(1, 10):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(HOST, username=USER, key_filename=key_path, timeout=25, banner_timeout=50)
            stdin, stdout, stderr = ssh.exec_command("mcp", timeout=30)
            break
        except Exception as e:
            try:
                ssh.close()
            except Exception:
                pass
            if attempt == 9:
                raise ConnectionError(f"Failed to connect and start MCP session after 9 attempts: {e}")
            print(f"[{client_label}] SSH attempt {attempt} failed ({e}), retrying in {attempt * 3}s...")
            time.sleep(attempt * 3.0)

    t = ssh.get_transport()
    if t:
        t.set_keepalive(5)

    def send_rpc(obj):
        time.sleep(0.3)
        line = json.dumps(obj) + "\n"
        stdin.write(line)
        stdin.flush()

    def read_rpc():
        line = stdout.readline()
        if not line:
            err = stderr.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"EOF received from stdio server. Stderr: {err}")
        return json.loads(line.strip())

    return ssh, send_rpc, read_rpc



def run_remote_py(code):
    cmd = f"""python3 -c "import sys; sys.path.insert(0, '/home/mcp-gateway/mcp-gateway/src'); {code}" """
    code_res, out, err = run_remote(cmd, as_user="mcp-gateway")
    if code_res != 0:
        raise RuntimeError(f"Remote command failed (code {code_res}): {err or out}")
    return out.strip()


def test_gemini_main_baseline():
    print("\n=======================================================")
    print("TEST 1: gemini-main Baseline Permissions (read,execute)")
    print("=======================================================")
    ssh, send_rpc, read_rpc = create_client_session("mcp_gemini_ed25519", "gemini-main")
    try:
        # 1. Initialize
        send_rpc({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2026-07-28", "capabilities": {}, "clientInfo": {"name": "gemini-main", "version": "1.0"}}
        })
        resp = read_rpc()
        proto_ver = resp.get("result", {}).get("protocolVersion")
        assert proto_ver in ("2026-07-28", "2025-11-25"), f"Unexpected init resp: {resp}"
        assert resp["result"]["serverInfo"]["name"] == "mcp-gateway-adapter"
        print(f"  [PASS] Initialize protocolVersion: {proto_ver}")

        # Initialized notification
        send_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})

        # 2. tools/list
        send_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        resp = read_rpc()
        tools = [t["name"] for t in resp.get("result", {}).get("tools", [])]
        print(f"  [INFO] gemini-main tools ({len(tools)}): {tools}")
        assert len(tools) == 8, f"Expected exactly 8 tools, got {len(tools)}: {tools}"
        assert "write_file" not in tools, "write_file MUST NOT be present in tools/list"
        assert "health" in tools
        assert "run_task" in tools
        assert "read_file" in tools
        print("  [PASS] tools/list returns exactly 8 tools without write_file")

        # 3. tools/call health
        send_rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "health", "arguments": {}}})
        resp = read_rpc()
        res = resp.get("result", {})
        assert res.get("isError") in (False, None), f"health failed: {res}"
        assert res.get("structuredContent", {}).get("ok") is True
        gw_status = res.get("structuredContent", {}).get("result", {}).get("gateway_status", "ok")
        print(f"  [PASS] health call succeeded: gateway_status={gw_status}")

        # 4. tools/call write_file (must be rejected)
        send_rpc({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "target": "termux-main",
                    "project": "write_smoke",
                    "relative_path": "unauthorized.txt",
                    "content": "test",
                    "create": True
                }
            }
        })
        resp = read_rpc()
        print(f"  [DEBUG] write_file response: {resp}")
        res = resp.get("result", {})
        err = resp.get("error", {})
        is_err = res.get("isError") is True or bool(err)
        assert is_err, f"write_file should have failed: {resp}"
        err_msg = err.get("message", "") or str(res.get("structuredContent", {}).get("error", ""))
        print(f"  [PASS] unauthorized write_file rejected as expected: {err_msg or resp}")
    finally:
        ssh.close()
    return True


def test_claude_desktop_baseline():
    print("\n=======================================================")
    print("TEST 2: claude-desktop Baseline Permissions (read only)")
    print("=======================================================")
    ssh, send_rpc, read_rpc = create_client_session("mcp_claude_ed25519", "claude-desktop")
    try:
        # 1. Initialize
        send_rpc({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2026-07-28", "capabilities": {}, "clientInfo": {"name": "claude-desktop", "version": "1.0"}}
        })
        resp = read_rpc()
        proto_ver = resp.get("result", {}).get("protocolVersion")
        assert proto_ver in ("2026-07-28", "2025-11-25"), f"Unexpected init resp: {resp}"
        print(f"  [PASS] Initialize protocolVersion: {proto_ver}")

        send_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})

        # 2. tools/list
        send_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        resp = read_rpc()
        tools = [t["name"] for t in resp.get("result", {}).get("tools", [])]
        print(f"  [INFO] claude-desktop tools ({len(tools)}): {tools}")
        assert "write_file" not in tools, "write_file MUST NOT be present"
        assert "run_task" not in tools, "run_task MUST NOT be present (claude only has read grant)"
        assert "health" in tools
        assert "read_file" in tools
        print("  [PASS] tools/list for claude-desktop contains read tools only (no write_file, no run_task)")

        # 3. tools/call health
        send_rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "health", "arguments": {}}})
        resp = read_rpc()
        res = resp.get("result", {})
        assert res.get("isError") in (False, None), f"health failed: {res}"
        print("  [PASS] health call succeeded for claude-desktop")

        # 4. tools/call write_file rejected
        send_rpc({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "target": "termux-main",
                    "project": "write_smoke",
                    "relative_path": "claude_bad.txt",
                    "content": "test",
                    "create": True
                }
            }
        })
        resp = read_rpc()
        print(f"  [DEBUG] claude write_file response: {resp}")
        res = resp.get("result", {})
        err = resp.get("error", {})
        is_err = res.get("isError") is True or bool(err)
        assert is_err, f"write_file should have failed for claude: {resp}"
        err_msg = err.get("message", "") or str(res.get("structuredContent", {}).get("error", ""))
        print(f"  [PASS] unauthorized write_file rejected for claude-desktop as expected: {err_msg or resp}")
    finally:
        ssh.close()
    return True


def test_dynamic_grants():
    print("\n=======================================================")
    print("TEST 3: Dynamic Grant Mutation and Verification")
    print("=======================================================")
    print("  -> Enabling global writes and adding temporary write grant to gemini-main...")
    add_grant_code = (
        "from mcp_gateway.registry import get_registry; "
        "r = get_registry(); "
        "r.set_setting('writes_enabled', 'true'); "
        "gid = r.add_grant({'client_id': 'gemini-main', 'capability': 'read,execute,write', 'target_id': '*', 'project_id': '*', 'enabled': True}); "
        "print('ADDED_GRANT_ID:', gid)"
    )
    out = run_remote_py(add_grant_code)
    grant_id = int(out.split("ADDED_GRANT_ID:")[1].strip())
    print(f"  [INFO] Temporary grant added with ID: {grant_id}")

    try:
        # Verify gemini-main now sees write_file in tools/list
        ssh, send_rpc, read_rpc = create_client_session("mcp_gemini_ed25519", "gemini-main")
        try:
            send_rpc({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2026-07-28"}
            })
            read_rpc()
            send_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})

            send_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            resp = read_rpc()
            tools = [t["name"] for t in resp.get("result", {}).get("tools", [])]
            print(f"  [INFO] gemini-main tools with write grant ({len(tools)}): {tools}")
            assert "write_file" in tools, "write_file MUST be in tools/list after write grant added"
            assert len(tools) == 9, f"Expected 9 tools, got {len(tools)}"
            print("  [PASS] write_file dynamically appears in tools/list after grant addition")
        finally:
            ssh.close()

    finally:
        print(f"  -> Revoking temporary grant ID {grant_id} and resetting writes_enabled...")
        cleanup_code = (
            f"from mcp_gateway.registry import get_registry; "
            f"r = get_registry(); "
            f"r.delete_grant({grant_id}); "
            f"r.set_setting('writes_enabled', 'false'); "
            f"print('CLEANED_UP')"
        )
        out = run_remote_py(cleanup_code)
        print(f"  [INFO] Cleanup status: {out}")

    # Verify gemini-main tools/list is back to 8 tools
    ssh, send_rpc, read_rpc = create_client_session("mcp_gemini_ed25519", "gemini-main")
    try:
        send_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2026-07-28"}})
        read_rpc()
        send_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        resp = read_rpc()
        tools = [t["name"] for t in resp.get("result", {}).get("tools", [])]
        assert "write_file" not in tools, "write_file MUST NOT be present after revocation"
        assert len(tools) == 8
        print("  [PASS] write_file dynamically removed from tools/list after grant revocation")
    finally:
        ssh.close()
    return True


def test_client_disable_lifecycle():
    print("\n=======================================================")
    print("TEST 4: Client Emergency Disablement & Reactivation")
    print("=======================================================")
    print("  -> Disabling client gemini-main in registry...")
    disable_code = (
        "from mcp_gateway.registry import get_registry; "
        "r = get_registry(); "
        "r.update_client('gemini-main', {'enabled': False}); "
        "print('DISABLED')"
    )
    run_remote_py(disable_code)

    try:
        # Verify gemini-main calls are rejected
        ssh, send_rpc, read_rpc = create_client_session("mcp_gemini_ed25519", "gemini-main")
        try:
            send_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2026-07-28"}})
            read_rpc()
            send_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})

            # tools/list should return 0 tools
            send_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            resp = read_rpc()
            tools = resp.get("result", {}).get("tools", [])
            assert len(tools) == 0, f"Expected 0 tools for disabled client, got {len(tools)}: {tools}"
            print("  [PASS] Disabled client receives empty tools catalog (0 tools)")

            # tools/call health should be rejected
            send_rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "health", "arguments": {}}})
            resp = read_rpc()
            print(f"  [DEBUG] disabled client call response: {resp}")
            res = resp.get("result", {})
            err = resp.get("error", {})
            is_err = res.get("isError") is True or bool(err)
            assert is_err, f"disabled client call should have failed: {resp}"
            err_msg = err.get("message", "") or str(res.get("structuredContent", {}).get("error", ""))
            print(f"  [PASS] Disabled client invocation rejected as expected: {err_msg or resp}")
        finally:
            ssh.close()

    finally:
        print("  -> Re-enabling client gemini-main in registry...")
        enable_code = (
            "from mcp_gateway.registry import get_registry; "
            "r = get_registry(); "
            "r.update_client('gemini-main', {'enabled': True}); "
            "print('RE_ENABLED')"
        )
        run_remote_py(enable_code)

    # Verify gemini-main restored
    ssh, send_rpc, read_rpc = create_client_session("mcp_gemini_ed25519", "gemini-main")
    try:
        send_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2026-07-28"}})
        read_rpc()
        send_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        resp = read_rpc()
        tools = [t["name"] for t in resp.get("result", {}).get("tools", [])]
        assert len(tools) == 8
        print("  [PASS] Client gemini-main successfully restored to normal operation (8 tools)")
    finally:
        ssh.close()
    return True


if __name__ == "__main__":
    t0 = time.time()
    print("===================================================================")
    print("STARTING PHASE 6A LIVE VERIFICATION SUITE")
    print(f"Target Gateway: {USER}@{HOST} (Raspberry Pi Model A+)")
    print("===================================================================")
    try:
        test_gemini_main_baseline()
        test_claude_desktop_baseline()
        test_dynamic_grants()
        test_client_disable_lifecycle()
        duration = time.time() - t0
        print("\n===================================================================")
        print(f"ALL PHASE 6A LIVE TESTS PASSED SUCCESSFULLY in {duration:.2f}s!")
        print("===================================================================")
        sys.exit(0)
    except Exception as e:
        print(f"\n[FATAL] Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

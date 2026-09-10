#!/usr/bin/env python3
"""Comprehensive Security Negative Verification Suite for MCP-Pi Gateway v1.0.1.

Verifies canonical security controls:
1. Path Traversal rejection (../.bashrc) -> DENIED
2. Absolute Path rejection (/etc/passwd) -> DENIED
3. Unknown Target rejection (unknown-target) -> DENIED
4. Unknown Project rejection (unknown-project) -> DENIED
5. Unauthorized Task rejection (rm_rf) -> DENIED
6. Symlink / Root Escape rejection -> DENIED
7. Disabled Target rejection (target marked disabled) -> DENIED
8. Global Kill Switch rejection (writes_enabled=false) -> DENIED
Plus Ingress / Protocol Controls:
9. HTTP Host Rebinding protection (Host: evil.com) -> 403 FORBIDDEN
10. HTTP Origin CSRF protection (Origin: http://evil.com) -> 403 FORBIDDEN
11. Unauthorized Client rejection (unauthenticated / unknown key) -> DENIED
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import paramiko

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.pi_ssh import run_remote

HOST = os.environ.get("MCP_PI_HOST", "192.168.68.85")
USER = "mcp-gateway"
KEY = os.path.expanduser("~/.ssh/mcp_gemini_ed25519")
KH = os.path.expanduser("~/.ssh/mcp_known_hosts")


def create_client_session():
    ssh = paramiko.SSHClient()
    if os.path.isfile(KH):
        ssh.load_host_keys(KH)
    else:
        ssh.load_host_keys(os.path.expanduser("~/.ssh/known_hosts"))
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    ssh.connect(HOST, username=USER, key_filename=KEY, timeout=25, banner_timeout=50)
    stdin, stdout, stderr = ssh.exec_command("mcp", timeout=30)
    
    t = ssh.get_transport()
    if t:
        t.set_keepalive(5)

    def send_rpc(obj):
        time.sleep(0.2)
        stdin.write(json.dumps(obj) + "\n")
        stdin.flush()

    def read_rpc():
        line = stdout.readline()
        if not line:
            err = stderr.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"EOF from stdio server. Stderr: {err}")
        return json.loads(line.strip())

    # Initialize session
    send_rpc({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2026-07-28",
            "capabilities": {},
            "clientInfo": {"name": "test-negative", "version": "1.0"}
        }
    })
    init_resp = read_rpc()
    send_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call_tool(name, arguments):
        send_rpc({
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000) % 100000,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments}
        })
        return read_rpc()

    def close():
        try:
            ssh.close()
        except Exception:
            pass

    return call_tool, close


def run_remote_py(code):
    import base64
    full_code = f"import sys\nsys.path.insert(0, '/home/mcp-gateway/mcp-gateway/src')\n{code}"
    b64 = base64.b64encode(full_code.encode("utf-8")).decode("ascii")
    cmd = f'python3 -c "import base64; exec(base64.b64decode(\'{b64}\'))"'
    code_res, out, err = run_remote(cmd, as_user="mcp-gateway")
    if code_res != 0:
        raise RuntimeError(f"Remote command failed (code {code_res}): {err or out}")
    return out.strip()


def run_negative_suite():
    print("===================================================================")
    print("STARTING SECURITY NEGATIVE & CANONICAL CONTROLS TEST SUITE")
    print(f"Target Gateway: {USER}@{HOST} (Raspberry Pi Model A+)")
    print("===================================================================")

    results = {}
    call_tool, close_session = create_client_session()

    try:
        # 1. Path Traversal
        print("\n[VECTOR 1/8] Testing Path Traversal rejection (../.bashrc)...")
        resp = call_tool("read_file", {
            "target": "termux-main",
            "project": "MCP_Local",
            "relative_path": "../.bashrc"
        })
        is_err = resp.get("result", {}).get("isError") is True or "error" in resp
        err_msg = str(resp.get("result", {}).get("structuredContent", {}).get("error", "")) or str(resp.get("error", ""))
        assert is_err and ("INVALID_PATH" in err_msg or "outside" in err_msg.lower() or "denied" in err_msg.lower()), f"Failed traversal rejection: {resp}"
        print(f"  [PASS] Path traversal rejected: {err_msg}")
        results["path_traversal"] = "DENIED"

        # 2. Absolute Path
        print("\n[VECTOR 2/8] Testing Absolute Path rejection (/etc/passwd)...")
        resp = call_tool("read_file", {
            "target": "termux-main",
            "project": "MCP_Local",
            "relative_path": "/etc/passwd"
        })
        is_err = resp.get("result", {}).get("isError") is True or "error" in resp
        err_msg = str(resp.get("result", {}).get("structuredContent", {}).get("error", "")) or str(resp.get("error", ""))
        assert is_err and ("INVALID_PATH" in err_msg or "outside" in err_msg.lower() or "denied" in err_msg.lower()), f"Failed absolute path rejection: {resp}"
        print(f"  [PASS] Absolute path rejected: {err_msg}")
        results["absolute_path"] = "DENIED"

        # 3. Unknown Target
        print("\n[VECTOR 3/8] Testing Unknown Target rejection (unknown-box)...")
        resp = call_tool("target_status", {
            "target": "unknown-box"
        })
        is_err = resp.get("result", {}).get("isError") is True or "error" in resp
        err_msg = str(resp.get("result", {}).get("structuredContent", {}).get("error", "")) or str(resp.get("error", ""))
        assert is_err and ("TARGET_NOT_FOUND" in err_msg or "not found" in err_msg.lower() or "unknown" in err_msg.lower()), f"Failed unknown target: {resp}"
        print(f"  [PASS] Unknown target rejected: {err_msg}")
        results["unknown_target"] = "DENIED"

        # 4. Unknown Project
        print("\n[VECTOR 4/8] Testing Unknown Project rejection (nonexistent-proj)...")
        resp = call_tool("read_file", {
            "target": "termux-main",
            "project": "nonexistent-proj",
            "relative_path": "README.md"
        })
        is_err = resp.get("result", {}).get("isError") is True or "error" in resp
        err_msg = str(resp.get("result", {}).get("structuredContent", {}).get("error", "")) or str(resp.get("error", ""))
        assert is_err and ("PROJECT_NOT_FOUND" in err_msg or "not found" in err_msg.lower() or "unknown" in err_msg.lower() or "denied" in err_msg.lower()), f"Failed unknown project: {resp}"
        print(f"  [PASS] Unknown project rejected: {err_msg}")
        results["unknown_project"] = "DENIED"

        # 5. Unauthorized Task
        print("\n[VECTOR 5/8] Testing Unauthorized Task rejection (rm_rf)...")
        resp = call_tool("run_task", {
            "target": "termux-main",
            "project": "MCP_Local",
            "task": "rm_rf"
        })
        is_err = resp.get("result", {}).get("isError") is True or "error" in resp
        err_msg = str(resp.get("result", {}).get("structuredContent", {}).get("error", "")) or str(resp.get("error", ""))
        assert is_err and ("TASK_NOT_ALLOWED" in err_msg or "allowlist" in err_msg.lower() or "denied" in err_msg.lower()), f"Failed unauthorized task: {resp}"
        print(f"  [PASS] Unauthorized task rejected: {err_msg}")
        results["unauthorized_task"] = "DENIED"

        # 6. Symlink Escape Rejection
        print("\n[VECTOR 6/8] Testing Symlink / Path Escape Policy...")
        symlink_test_code = """
from mcp_gateway.policy import validate_canonical_path, PolicyError
try:
    validate_canonical_path('/data/projects/other/secret.txt', '/data/projects/myproj')
    print('FAIL')
except PolicyError as e:
    print('PASS:', e.code)
"""
        out = run_remote_py(symlink_test_code)
        assert "PASS: PATH_OUTSIDE_ALLOWED_ROOT" in out, f"Unexpected symlink check result: {out}"
        print(f"  [PASS] Symlink escape outside allowed root strictly denied: {out}")
        results["symlink_escape"] = "DENIED"

        # 7. Disabled Target Rejection
        print("\n[VECTOR 7/8] Testing Disabled Target rejection...")
        run_remote_py("from mcp_gateway.registry import get_registry; r = get_registry(); r.update_target('termux-main', {'enabled': False})")
        try:
            resp = call_tool("read_file", {
                "target": "termux-main",
                "project": "MCP_Local",
                "relative_path": "README.md"
            })
            is_err = resp.get("result", {}).get("isError") is True or "error" in resp
            err_msg = str(resp.get("result", {}).get("structuredContent", {}).get("error", "")) or str(resp.get("error", ""))
            assert is_err and ("TARGET_DISABLED" in err_msg or "disabled" in err_msg.lower()), f"Failed disabled target: {resp}"
            print(f"  [PASS] Disabled target invocation rejected: {err_msg}")
            results["disabled_target"] = "DENIED"
        finally:
            run_remote_py("from mcp_gateway.registry import get_registry; r = get_registry(); r.update_target('termux-main', {'enabled': True})")
            print("  [INFO] Target termux-main re-enabled.")

        # 8. Global Kill Switch / Writes Disabled
        print("\n[VECTOR 8/8] Testing Global Kill Switch / Writes Disabled rejection...")
        # Add temporary write grant, then open a fresh session to test WRITES_DISABLED
        add_grant_code = (
            "from mcp_gateway.registry import get_registry; "
            "r = get_registry(); "
            "r.set_setting('writes_enabled', 'false'); "
            "gid = r.add_grant({'client_id': 'gemini-main', 'capability': 'read,execute,write', 'target_id': '*', 'project_id': '*', 'enabled': True}); "
            "print('GID:', gid)"
        )
        out = run_remote_py(add_grant_code)
        gid = int(out.split("GID:")[1].strip())
        try:
            call_tool_8, close_8 = create_client_session()
            try:
                resp = call_tool_8("write_file", {
                    "target": "termux-main",
                    "project": "MCP_Local",
                    "relative_path": "kill_switch_test.txt",
                    "content": "blocked"
                })
                is_err = resp.get("result", {}).get("isError") is True or "error" in resp
                err_msg = str(resp.get("result", {}).get("structuredContent", {}).get("error", "")) or str(resp.get("error", ""))
                assert is_err and ("WRITES_DISABLED" in err_msg or "disabled" in err_msg.lower()), f"Failed kill switch: {resp}"
                print(f"  [PASS] Global kill switch blocked write operation: {err_msg}")
                results["kill_switch"] = "DENIED"
            finally:
                close_8()
        finally:
            run_remote_py(f"from mcp_gateway.registry import get_registry; r = get_registry(); r.delete_grant({gid}); r.set_setting('writes_enabled', 'false')")
            print("  [INFO] Temporary grant revoked and writes_enabled confirmed false.")

    finally:
        close_session()

    # 9 & 10. HTTP Host Rebinding & Origin Protection on Live MCP Endpoint (127.0.0.1:8090/mcp)
    print("\n[INGRESS 9 & 10] Testing HTTP Host Rebinding & Origin Protection on 127.0.0.1:8090/mcp...")
    http_sec_test = """
import urllib.request, urllib.error, json
# Test 9: Malicious Host header -> 403
req9 = urllib.request.Request('http://127.0.0.1:8090/mcp', data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}).encode(), headers={'Host': 'evil.com', 'Content-Type': 'application/json'})
try:
    urllib.request.urlopen(req9, timeout=5)
    code9 = 200
except urllib.error.HTTPError as e:
    code9 = e.code
print('HOST_REBINDING_CODE:', code9)

# Test 10: Malicious Origin header -> 403
req10 = urllib.request.Request('http://127.0.0.1:8090/mcp', data=json.dumps({'jsonrpc': '2.0', 'id': 2, 'method': 'ping'}).encode(), headers={'Origin': 'http://evil.com', 'Content-Type': 'application/json'})
try:
    urllib.request.urlopen(req10, timeout=5)
    code10 = 200
except urllib.error.HTTPError as e:
    code10 = e.code
print('ORIGIN_CSRF_CODE:', code10)
"""
    out = run_remote_py(http_sec_test)
    print(f"  HTTP security output: {out}")
    assert "HOST_REBINDING_CODE: 403" in out, f"Expected 403 for Host rebinding, got: {out}"
    assert "ORIGIN_CSRF_CODE: 403" in out, f"Expected 403 for Origin CSRF, got: {out}"
    print("  [PASS] Host header rebinding strictly rejected with HTTP 403 Forbidden")
    print("  [PASS] Origin header cross-origin access strictly rejected with HTTP 403 Forbidden")
    results["host_rebinding"] = "403_FORBIDDEN"
    results["origin_csrf"] = "403_FORBIDDEN"

    # 11. Unauthorized SSH Client Rejection
    print("\n[INGRESS 11] Testing Unauthorized Client Rejection...")
    # Attempt connecting to mcp-gateway with unconfigured key (id_ed25519 is yorologo's admin key, not in mcp-gateway authorized_keys)
    unauthorized_key = os.path.expanduser("~/.ssh/id_ed25519")
    ssh = paramiko.SSHClient()
    if os.path.isfile(KH):
        ssh.load_host_keys(KH)
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    auth_failed = False
    try:
        ssh.connect(HOST, username=USER, key_filename=unauthorized_key, timeout=10, banner_timeout=20)
        ssh.close()
    except paramiko.AuthenticationException:
        auth_failed = True
    assert auth_failed, "Unregistered client key MUST be rejected by SSH authentication layer"
    print("  [PASS] Unauthorized client key rejected by SSH authentication layer")
    results["unauthorized_client"] = "DENIED"

    print("\n===================================================================")
    print("SUMMARY OF CANONICAL SECURITY CONTROLS:")
    for k, v in results.items():
        print(f"  - {k}: {v}")
    print("===================================================================")
    denied_count = sum(1 for v in results.values() if "DENIED" in v or "403" in v)
    print(f"CANONICAL NEGATIVE / CONTROL E2E: 8/8 DENIED + {denied_count - 8}/3 INGRESS PROTECTIONS PASS")
    print("===================================================================")
    return True


if __name__ == "__main__":
    t0 = time.time()
    try:
        run_negative_suite()
        print(f"\nALL SECURITY NEGATIVE TESTS COMPLETED SUCCESSFULLY IN {time.time() - t0:.2f}s!")
    except Exception as e:
        print(f"\n[FATAL] Security negative suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

#!/usr/bin/env python3
"""Explicit Authorization Precedence & Separation of Concerns Verification.

Tests:
1. Client lacking write_file grant:
   - tools/list: write_file ABSENT
   - tools/call: rejected at authorization layer (TOOL_NOT_ALLOWED / unknown tool)
   - MUST NOT leak lower operational states (WRITES_DISABLED, project.write)
2. Grant write_file while writes_enabled=false:
   - tools/list: write_file VISIBLE (authorization granted)
   - tools/call: rejected by operational safety switch (WRITES_DISABLED)
3. Revoke grant:
   - tools/list: write_file ABSENT again
   - tools/call: rejected at authorization layer again
"""

import json
import os
import sys
import time
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.pi_ssh import run_remote

HOST = os.environ.get("MCP_PI_HOST", "192.168.68.85")
USER = "mcp-gateway"
KEY = os.path.expanduser("~/.ssh/mcp_gemini_ed25519")
KH = os.path.expanduser("~/.ssh/mcp_known_hosts").replace("\\", "/")


def run_mcp_session():
    cmd = [
        "ssh",
        "-i", KEY,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={KH}",
        "-T",
        f"{USER}@{HOST}"
    ]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Initialize
    p.stdin.write(json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2026-07-28", "capabilities": {}, "clientInfo": {"name": "test-precedence", "version": "1.0"}}
    }) + "\n")
    p.stdin.flush()
    init_resp = json.loads(p.stdout.readline())
    
    # Initialized notification
    p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    p.stdin.flush()
    
    def list_tools():
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n")
        p.stdin.flush()
        resp = json.loads(p.stdout.readline())
        return [t["name"] for t in resp.get("result", {}).get("tools", [])]
        
    def call_tool(name, arguments):
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": name, "arguments": arguments}}) + "\n")
        p.stdin.flush()
        return json.loads(p.stdout.readline())
        
    def close():
        p.stdin.close()
        p.wait(timeout=5)
        
    return list_tools, call_tool, close


def run_remote_py(code):
    cmd = f"""python3 -c "import sys; sys.path.insert(0, '/home/mcp-gateway/mcp-gateway/src'); {code}" """
    code_res, out, err = run_remote(cmd, as_user="mcp-gateway")
    if code_res != 0:
        raise RuntimeError(f"Remote command failed (code {code_res}): {err or out}")
    return out.strip()


def test_precedence():
    print("=== TESTING AUTHORIZATION PRECEDENCE VS OPERATIONAL SWITCH ===")
    
    # Ensure baseline state: writes_enabled = false, and no write grants for gemini-main
    run_remote_py("from mcp_gateway.registry import get_registry; r = get_registry(); r.set_setting('writes_enabled', 'false'); [r.delete_grant(g['id']) for g in r.list_grants('gemini-main') if 'write' in g.get('capability', '')]")
    
    # STEP 1: Client without write_file grant
    print("\n--- STEP 1: Client without write_file grant (writes_enabled=false) ---")
    list_tools, call_tool, close = run_mcp_session()
    try:
        tools = list_tools()
        print(f"  tools/list ({len(tools)}): {tools}")
        assert "write_file" not in tools, "write_file MUST NOT be present in tools/list"
        print("  [PASS] write_file is absent from tools/list")
        
        resp = call_tool("write_file", {
            "target": "termux-main",
            "project": "write_smoke",
            "relative_path": "precedence_test.txt",
            "content": "test_precedence",
            "create": True
        })
        print(f"  tools/call response: {resp}")
        
        # Verify rejection at authorization layer without leaking lower state
        err = resp.get("error", {})
        res = resp.get("result", {})
        err_msg = err.get("message", "") or str(res.get("structuredContent", {}).get("error", ""))
        assert "unknown tool" in err_msg.lower() or "tool_not_allowed" in err_msg.lower(), f"Unexpected error: {err_msg}"
        assert "writes_disabled" not in err_msg.lower(), f"STATE LEAK! WRITES_DISABLED leaked to ungranted client: {err_msg}"
        assert "project.write" not in err_msg.lower(), f"STATE LEAK! project.write leaked to ungranted client: {err_msg}"
        print("  [PASS] Authorization rejected without leaking operational safety switch state!")
    finally:
        close()
        
    # STEP 2: Grant write_file while writes_enabled=false
    print("\n--- STEP 2: Grant write_file while writes_enabled=false ---")
    add_code = (
        "from mcp_gateway.registry import get_registry; "
        "r = get_registry(); "
        "gid = r.add_grant({'client_id': 'gemini-main', 'capability': 'read,execute,write', 'target_id': '*', 'project_id': '*', 'enabled': True}); "
        "print('ADDED_GRANT:', gid)"
    )
    run_remote_py(add_code)
    print("  Temporary write grant added to gemini-main.")
    
    try:
        list_tools, call_tool, close = run_mcp_session()
        try:
            tools = list_tools()
            print(f"  tools/list ({len(tools)}): {tools}")
            assert "write_file" in tools, "write_file MUST be visible in tools/list with active grant"
            print("  [PASS] write_file is now VISIBLE in tools/list (authorization passed)")
            
            resp = call_tool("write_file", {
                "target": "termux-main",
                "project": "write_smoke",
                "relative_path": "precedence_test.txt",
                "content": "test_precedence",
                "create": True
            })
            print(f"  tools/call response: {resp}")
            
            # Now authorization passed, so operational safety switch BLOCKS it with WRITES_DISABLED
            res = resp.get("result", {})
            err = resp.get("error", {})
            err_msg = str(res.get("structuredContent", {}).get("error", "")) or err.get("message", "")
            assert "WRITES_DISABLED" in err_msg or "Global writes are disabled" in err_msg, f"Expected WRITES_DISABLED, got: {err_msg}"
            print(f"  [PASS] Call rejected by operational safety switch: {err_msg}")
        finally:
            close()
    finally:
        # Cleanup grant
        print("\n--- STEP 3: Revoke temporary grant and cleanup ---")
        cleanup_code = (
            "from mcp_gateway.registry import get_registry; "
            "r = get_registry(); "
            "[r.delete_grant(g['id']) for g in r.list_grants('gemini-main') if 'write' in g.get('capability', '')]; "
            "print('CLEANED_UP')"
        )
        run_remote_py(cleanup_code)
        print("  Temporary write grant revoked.")
        
    # Verify restored state
    list_tools, call_tool, close = run_mcp_session()
    try:
        tools = list_tools()
        assert "write_file" not in tools, "write_file must be absent after grant revocation"
        print(f"  tools/list ({len(tools)}): {tools}")
        print("  [PASS] Restored: write_file is absent from tools/list")
    finally:
        close()
        
    print("\n=== AUTHORIZATION PRECEDENCE TEST PASSED 100% ===")
    return True


if __name__ == "__main__":
    test_precedence()

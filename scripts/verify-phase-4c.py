#!/usr/bin/env python3
"""E2E verification of Phase 4C: Official Go MCP Adapter on MCP-Pi."""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

ADAPTER_BIN = "/home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter"
PYTHON_BIN = "/usr/bin/python3"
SRC_DIR = "/home/mcp-gateway/mcp-gateway/src"
DB_PATH = "/home/mcp-gateway/.local/share/mcp-gateway/gateway.db"
HTTP_URL = "http://127.0.0.1:8090/mcp"


def run_stdio_interaction(requests):
    """Run a sequence of JSON-RPC requests over stdio and return responses."""
    p = subprocess.Popen(
        [ADAPTER_BIN, "-transport", "stdio", "-python", PYTHON_BIN, "-pythonpath", SRC_DIR],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    responses = []
    for req in requests:
        p.stdin.write(json.dumps(req) + "\n")
        p.stdin.flush()
        if "id" in req:
            line = p.stdout.readline()
            try:
                responses.append(json.loads(line))
            except Exception as e:
                responses.append({"error": f"Failed to parse JSON: {e}, raw: {line}"})

    p.terminate()
    p.wait()
    return responses


def send_http_mcp(req_obj):
    """Send a JSON-RPC request to Streamable HTTP endpoint."""
    data = json.dumps(req_obj).encode()
    req = urllib.request.Request(HTTP_URL, data=data, headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    })
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode()
        latency_ms = (time.monotonic() - t0) * 1000
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                return json.loads(line[5:].strip()), latency_ms
        return json.loads(body), latency_ms


def main():
    print("================================================================")
    print("=== MCP PI PHASE 4C: OFFICIAL MCP PROTOCOL ADAPTER E2E SUITE ===")
    print("================================================================\n")

    # 1. Stdio Mode Verification
    print("--- 1. STDIO MODE VERIFICATION ---")
    stdio_reqs = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2026-07-28",
                "capabilities": {},
                "clientInfo": {"name": "test-suite", "version": "1.0.0"}
            }
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "health", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "target_status", "arguments": {"target": "termux-main"}}},
    ]

    t0 = time.monotonic()
    stdio_resps = run_stdio_interaction(stdio_reqs)
    stdio_total_time = (time.monotonic() - t0) * 1000

    init_res = stdio_resps[0]
    p_ver = init_res.get("result", {}).get("protocolVersion")
    print(f"1.1 Stdio Init: protocolVersion={p_ver}")
    assert p_ver in ("2026-07-28", "2025-11-25"), f"Unexpected version: {init_res}"

    list_res = stdio_resps[1]
    tool_names = [t["name"] for t in list_res.get("result", {}).get("tools", [])]
    print(f"1.2 Stdio Discovery ({len(tool_names)} tools): {tool_names}")
    assert len(tool_names) == 8, f"Expected 8 tools, got {tool_names}"

    health_res = stdio_resps[2]
    health_text = health_res.get("result", {}).get("content", [{}])[0].get("text", "")
    print(f"1.3 Stdio Health Result: {health_text}")
    assert "gateway_status" in health_text

    status_res = stdio_resps[3]
    status_text = status_res.get("result", {}).get("content", [{}])[0].get("text", "")
    print(f"1.4 Stdio Target Status Result: {status_text}")
    assert "reachable" in status_text

    print(f"Stdio verification PASS (total session time: {stdio_total_time:.1f}ms)\n")

    # 2. Streamable HTTP Mode Verification
    print("--- 2. STREAMABLE HTTP MODE VERIFICATION (http://127.0.0.1:8090/mcp) ---")
    # Health endpoint
    with urllib.request.urlopen("http://127.0.0.1:8090/health") as resp:
        h_body = resp.read().decode()
        print(f"2.1 HTTP GET /health: {h_body}")
        assert resp.status == 200

    # Initialize via HTTP
    http_init, init_lat = send_http_mcp({
        "jsonrpc": "2.0",
        "id": 101,
        "method": "initialize",
        "params": {
            "protocolVersion": "2026-07-28",
            "capabilities": {},
            "clientInfo": {"name": "http-client", "version": "1.0.0"}
        }
    })
    print(f"2.2 HTTP Initialize ({init_lat:.1f}ms): {http_init.get('result', {}).get('serverInfo')}")
    assert "result" in http_init

    # Tools list via HTTP
    http_list, list_lat = send_http_mcp({"jsonrpc": "2.0", "id": 102, "method": "tools/list", "params": {}})
    http_tools = [t["name"] for t in http_list.get("result", {}).get("tools", [])]
    print(f"2.3 HTTP Discovery ({list_lat:.1f}ms): {http_tools}")
    assert len(http_tools) == 8

    # 3. All 8 Tools Positive Calls via HTTP MCP
    print("\n--- 3. POSITIVE VERIFICATION OF ALL 8 TOOLS VIA MCP ---")
    test_cases = [
        ("health", {}),
        ("list_targets", {}),
        ("target_status", {"target": "termux-main"}),
        ("list_directory", {"target": "termux-main", "project": "MCP_Local", "relative_path": "."}),
        ("file_stat", {"target": "termux-main", "project": "MCP_Local", "relative_path": "README.md"}),
        ("read_file", {"target": "termux-main", "project": "MCP_Local", "relative_path": "README.md"}),
        ("git_status", {"target": "termux-main", "project": "MCP_Local"}),
        ("run_task", {"target": "termux-main", "project": "MCP_Local", "task": "git_status"}),
    ]

    for tool_name, args in test_cases:
        call_req = {
            "jsonrpc": "2.0",
            "id": 200 + len(tool_name),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args}
        }
        res, lat = send_http_mcp(call_req)
        assert not res["result"].get("isError", False), f"Tool {tool_name} failed: {res}"
        content_text = res["result"]["content"][0]["text"]
        payload = json.loads(content_text)
        assert payload.get("ok") is True, f"Tool {tool_name} returned ok=false: {payload}"
        print(f"  Tool '{tool_name}' ({lat:.1f}ms): PASS (ok=true)")

    # 4. Negative Security Tests via HTTP MCP
    print("\n--- 4. NEGATIVE SECURITY TESTS VIA MCP ---")
    neg_cases = [
        ("Traversal rejection", "read_file", {"target": "termux-main", "project": "MCP_Local", "relative_path": "../.bashrc"}, "INVALID_PATH"),
        ("Absolute path rejection", "read_file", {"target": "termux-main", "project": "MCP_Local", "relative_path": "/etc/passwd"}, "INVALID_PATH"),
        ("Unknown target rejection", "target_status", {"target": "unknown-target-box"}, "UNKNOWN_TARGET"),
        ("Unknown project rejection", "list_directory", {"target": "termux-main", "project": "non_existent_proj"}, "UNKNOWN_PROJECT"),
        ("Unknown task rejection", "run_task", {"target": "termux-main", "project": "MCP_Local", "task": "rm_rf"}, "TASK_NOT_ALLOWED"),
    ]

    for label, tool_name, args, expected_code in neg_cases:
        call_req = {
            "jsonrpc": "2.0",
            "id": 300,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args}
        }
        res, lat = send_http_mcp(call_req)
        content_text = res["result"]["content"][0]["text"]
        payload = json.loads(content_text)
        actual_code = payload.get("error", {}).get("code")
        assert res["result"].get("isError") is True, f"{label} expected isError=true"
        assert actual_code == expected_code, f"{label} expected {expected_code}, got {actual_code}"
        print(f"  {label} ({lat:.1f}ms): DENIED (code={actual_code})")

    # Symlink escape test
    link_path = "/data/data/com.termux/files/home/Projects/test/MCP_Local/mcp_escape_symlink"
    try:
        # Create temporary escape symlink on target
        subprocess.run(["ssh", "pc-local", f"ln -sf /data/data/com.termux/files/home {link_path}"], check=False)
        call_req = {
            "jsonrpc": "2.0",
            "id": 310,
            "method": "tools/call",
            "params": {
                "name": "read_file",
                "arguments": {"target": "termux-main", "project": "MCP_Local", "relative_path": "mcp_escape_symlink/.bashrc"}
            }
        }
        res, lat = send_http_mcp(call_req)
        content_text = res["result"]["content"][0]["text"]
        payload = json.loads(content_text)
        actual_code = payload.get("error", {}).get("code")
        assert actual_code == "PATH_OUTSIDE_ALLOWED_ROOT", f"Expected PATH_OUTSIDE_ALLOWED_ROOT, got {actual_code}"
        print(f"  Symlink escape rejection ({lat:.1f}ms): DENIED (code={actual_code})")
    finally:
        subprocess.run(["ssh", "pc-local", f"rm -f {link_path}"], check=False)

    # 5. Kill Switch & Target Disable E2E Tests via MCP
    print("\n--- 5. KILL SWITCH & TARGET DISABLE VIA MCP ---")
    import sqlite3

    # Target disable
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE targets SET enabled = 0 WHERE id = 'termux-main'")
    res, _ = send_http_mcp({"jsonrpc": "2.0", "id": 401, "method": "tools/call", "params": {"name": "target_status", "arguments": {"target": "termux-main"}}})
    payload = json.loads(res["result"]["content"][0]["text"])
    assert payload.get("error", {}).get("code") == "TARGET_DISABLED"
    print("  Target disable test: DENIED (code=TARGET_DISABLED)")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE targets SET enabled = 1 WHERE id = 'termux-main'")
    res, _ = send_http_mcp({"jsonrpc": "2.0", "id": 402, "method": "tools/call", "params": {"name": "target_status", "arguments": {"target": "termux-main"}}})
    payload = json.loads(res["result"]["content"][0]["text"])
    assert payload.get("ok") is True
    print("  Target re-enable test: PASS (ok=true)")

    # Global kill switch
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE settings SET value = 'false' WHERE key = 'gateway_enabled'")
    res, _ = send_http_mcp({"jsonrpc": "2.0", "id": 403, "method": "tools/call", "params": {"name": "target_status", "arguments": {"target": "termux-main"}}})
    payload = json.loads(res["result"]["content"][0]["text"])
    assert payload.get("error", {}).get("code") == "GATEWAY_DISABLED"
    print("  Global Kill Switch test: DENIED (code=GATEWAY_DISABLED)")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE settings SET value = 'true' WHERE key = 'gateway_enabled'")
    res, _ = send_http_mcp({"jsonrpc": "2.0", "id": 404, "method": "tools/call", "params": {"name": "target_status", "arguments": {"target": "termux-main"}}})
    payload = json.loads(res["result"]["content"][0]["text"])
    assert payload.get("ok") is True
    print("  Global Kill Switch restoration test: PASS (ok=true)")

    # 6. Admin Console Integration Check
    print("\n--- 6. ADMIN CONSOLE INTEGRATION CHECK ---")
    with urllib.request.urlopen("http://127.0.0.1:8080/login") as resp:
        assert resp.status == 200
        print("  Admin Console is accessible on http://127.0.0.1:8080 (HTTP 200)")

    # 7. Resource Measurements
    print("\n--- 7. RESOURCE MEASUREMENTS ON MCP-PI ---")
    adapter_pid = subprocess.check_output(["pgrep", "-f", "mcp-gateway-adapter"]).decode().split()[0]
    admin_pid = subprocess.check_output(["pgrep", "-f", "mcp_gateway.web"]).decode().split()[0]
    
    ps_adapter = subprocess.check_output(["ps", "-o", "pid,user,vsz,rss,comm", "-p", adapter_pid]).decode().strip()
    ps_admin = subprocess.check_output(["ps", "-o", "pid,user,vsz,rss,comm", "-p", admin_pid]).decode().strip()
    bin_size = os.path.getsize(ADAPTER_BIN)

    print(f"Go Adapter Process:\n  {ps_adapter}")
    print(f"Admin Console Process:\n  {ps_admin}")
    print(f"Adapter Binary Size: {bin_size} bytes ({bin_size / (1024*1024):.2f} MB)")

    print("\n================================================================")
    print("=== ALL PHASE 4C MCP PROTOCOL VERIFICATIONS PASSED 100%! ===")
    print("================================================================")


if __name__ == "__main__":
    main()

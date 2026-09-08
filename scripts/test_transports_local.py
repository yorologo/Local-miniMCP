#!/usr/bin/env python3
"""E2E verification of MCP Gateway Adapter (stdio & Streamable HTTP) and Core Security."""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

ADAPTER_BIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp-adapter", "mcp-gateway-adapter"))
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))


def test_stdio():
    print("=== TEST STDIO TRANSPORT ===")
    p = subprocess.Popen(
        [ADAPTER_BIN, "-transport", "stdio", "-python", sys.executable, "-pythonpath", SRC_DIR],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    def send_recv(msg):
        p.stdin.write(json.dumps(msg) + "\n")
        p.stdin.flush()
        line = p.stdout.readline()
        return json.loads(line) if line else None

    # 1. Initialize
    init_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2026-07-28",
            "capabilities": {},
            "clientInfo": {"name": "test-stdio", "version": "1.0.0"}
        }
    }
    res_init = send_recv(init_msg)
    print("Init response:", json.dumps(res_init, indent=2))
    assert res_init and "result" in res_init, f"Init failed: {res_init}"

    # Initialized notification
    p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    p.stdin.flush()

    # 2. List tools
    list_msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    res_list = send_recv(list_msg)
    tools = res_list.get("result", {}).get("tools", [])
    print(f"Discovered {len(tools)} tools: {[t['name'] for t in tools]}")
    assert len(tools) == 8, f"Expected 8 tools, got {len(tools)}"

    # 3. Call health
    call_health = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "health", "arguments": {}}
    }
    t0 = time.monotonic()
    res_health = send_recv(call_health)
    latency_ms = (time.monotonic() - t0) * 1000
    print(f"Health call ({latency_ms:.1f}ms):", json.dumps(res_health, indent=2))
    assert res_health and "result" in res_health
    assert not res_health["result"].get("isError", False)

    p.terminate()
    p.wait()
    print("Stdio test passed!\n")


def test_http():
    print("=== TEST STREAMABLE HTTP TRANSPORT ===")
    port = 18092
    p = subprocess.Popen(
        [ADAPTER_BIN, "-transport", "http", "-bind", f"127.0.0.1:{port}", "-python", sys.executable, "-pythonpath", SRC_DIR],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(0.5)

    # 1. Test GET /health
    url_health = f"http://127.0.0.1:{port}/health"
    req = urllib.request.Request(url_health)
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode()
        print("GET /health:", body)
        assert resp.status == 200

    # 2. Test POST /mcp initialize
    url_mcp = f"http://127.0.0.1:{port}/mcp"
    init_payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2026-07-28",
            "capabilities": {},
            "clientInfo": {"name": "test-http", "version": "1.0.0"}
        }
    }).encode()

    req_init = urllib.request.Request(url_mcp, data=init_payload, headers={
        "Content-Type": "application/json",
        "Accept": "application/json"
    })
    try:
        with urllib.request.urlopen(req_init) as resp:
            body = resp.read().decode()
            print("POST /mcp initialize response:", body)
            assert resp.status == 200
    except urllib.error.HTTPError as e:
        print("HTTP Error:", e.code, e.read().decode())
        raise

    # 3. Test POST /mcp tools/call health
    call_payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "health", "arguments": {}}
    }).encode()

    t0 = time.monotonic()
    req_call = urllib.request.Request(url_mcp, data=call_payload, headers={
        "Content-Type": "application/json",
        "Accept": "application/json"
    })
    with urllib.request.urlopen(req_call) as resp:
        body = resp.read().decode()
        latency_ms = (time.monotonic() - t0) * 1000
        print(f"POST /mcp tools/call health ({latency_ms:.1f}ms):", body)
        assert resp.status == 200
        data = json.loads(body)
        assert "result" in data
        assert not data["result"].get("isError", False)

    p.terminate()
    p.wait()
    print("HTTP test passed!\n")


if __name__ == "__main__":
    test_stdio()
    test_http()

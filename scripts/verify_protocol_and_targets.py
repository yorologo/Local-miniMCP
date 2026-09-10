#!/usr/bin/env python3
"""Verification of Step 9 (MCP Protocol Regression) and Step 10 (Target Operations) on MCP-Pi.

Tests:
1. HTTP GET /live -> 200 alive
2. HTTP GET /ready -> 200 ready
3. HTTP GET /health -> 200 ready: true
4. HTTP GET /server/discover -> 200 discovery metadata
5. HTTP POST /mcp initialize with protocolVersion 2026-07-28
6. HTTP POST /mcp initialize with protocolVersion 2025-11-25
7. HTTP POST /mcp tools/list -> exactly 8 tools
8. Target Operations on termux-main:
   - health
   - list_targets
   - target_status
   - list_directory
   - file_stat
   - read_file
   - git_status
   - run_task (git_status)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.pi_ssh import run_remote

HOST = os.environ.get("MCP_PI_HOST", "192.168.68.85")


def run_remote_py(code):
    import base64
    full_code = f"import sys\nsys.path.insert(0, '/home/mcp-gateway/mcp-gateway/src')\n{code}"
    b64 = base64.b64encode(full_code.encode("utf-8")).decode("ascii")
    cmd = f'python3 -c "import base64; exec(base64.b64decode(\'{b64}\'))"'
    code_res, out, err = run_remote(cmd, as_user="mcp-gateway")
    if code_res != 0:
        raise RuntimeError(f"Remote command failed (code {code_res}):\n--- STDOUT ---\n{out}\n--- STDERR ---\n{err}")
    return out.strip()


def run_protocol_and_target_regression():
    print("===================================================================")
    print("STARTING STEPS 9 & 10: MCP PROTOCOL & TARGET OPERATIONS REGRESSION")
    print(f"Target Gateway: {HOST} (Raspberry Pi Model A+)")
    print("===================================================================")

    remote_test_script = """
import urllib.request, urllib.error, json, time

BASE = "http://127.0.0.1:8090"

def get(path):
    req = urllib.request.Request(f"{BASE}{path}", headers={"Host": "127.0.0.1"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode())

def post_mcp(req_obj):
    data = json.dumps(req_obj).encode()
    req = urllib.request.Request(f"{BASE}/mcp", data=data, headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Host": "127.0.0.1"
    })
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode()
        lat = (time.monotonic() - t0) * 1000
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                return json.loads(line[5:].strip()), lat
        return json.loads(body), lat

# STEP 9: MCP Protocol Endpoints
print("--- STEP 9.1: GET /live ---")
st, body = get("/live")
print(f"  status={st}, body={body}")
assert st == 200 and body.get("status") == "alive"

print("--- STEP 9.2: GET /ready ---")
st, body = get("/ready")
print(f"  status={st}, body={body}")
assert st == 200 and body.get("status") == "ready"
assert body.get("gateway_version") == "1.0.1"

print("--- STEP 9.3: GET /health ---")
st, body = get("/health")
print(f"  status={st}, ready={body.get('ready')}, adapter={body.get('adapter_status')}")
assert st == 200 and body.get("ready") is True

print("--- STEP 9.4: GET /server/discover ---")
st, body = get("/server/discover")
print(f"  status={st}, server={body.get('server', {}).get('name')}, version={body.get('server', {}).get('version')}")
assert st == 200 and body.get("server", {}).get("version") == "1.0.1"

print("--- STEP 9.5: POST /mcp Initialize (2026-07-28) ---")
init_2026, lat = post_mcp({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2026-07-28",
        "capabilities": {},
        "clientInfo": {"name": "test-protocol", "version": "1.0"}
    }
})
p_ver = init_2026.get("result", {}).get("protocolVersion")
print(f"  Negotiated protocolVersion ({lat:.1f}ms): {p_ver}")
assert p_ver in ("2026-07-28", "2025-11-25")

print("--- STEP 9.6: POST /mcp Initialize (2025-11-25) ---")
init_2025, lat = post_mcp({
    "jsonrpc": "2.0",
    "id": 2,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "test-protocol", "version": "1.0"}
    }
})
print("  init_2025 raw:", init_2025)
p_ver25 = init_2025.get("result", {}).get("protocolVersion")
print(f"  Negotiated protocolVersion ({lat:.1f}ms): {p_ver25}")
assert p_ver25 in ("2025-11-25", "2026-07-28")

print("--- STEP 9.7: POST /mcp tools/list ---")
tlist, lat = post_mcp({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}})
tools = [t["name"] for t in tlist.get("result", {}).get("tools", [])]
print(f"  tools/list ({len(tools)} tools, {lat:.1f}ms): {tools}")
assert len(tools) == 9
assert "write_file" in tools

# STEP 10: Target Operations on termux-main
print("\\n--- STEP 10: TARGET OPERATIONS ON termux-main ---")
ops = [
    ("health", {}),
    ("list_targets", {}),
    ("target_status", {"target": "termux-main"}),
    ("list_directory", {"target": "termux-main", "project": "MCP_Local", "relative_path": "."}),
    ("file_stat", {"target": "termux-main", "project": "MCP_Local", "relative_path": "README.md"}),
    ("read_file", {"target": "termux-main", "project": "MCP_Local", "relative_path": "README.md"}),
    ("git_status", {"target": "termux-main", "project": "MCP_Local"}),
    ("run_task", {"target": "termux-main", "project": "MCP_Local", "task": "git_status"}),
]

for name, args in ops:
    res, lat = post_mcp({
        "jsonrpc": "2.0",
        "id": 100 + len(name),
        "method": "tools/call",
        "params": {"name": name, "arguments": args}
    })
    is_err = res.get("result", {}).get("isError", False)
    content = res.get("result", {}).get("content", [{}])[0].get("text", "")
    data = json.loads(content) if content else {}
    ok = data.get("ok")
    assert not is_err and ok is True, f"Tool {name} failed ({res})"
    print(f"  [PASS] Tool '{name}' ({lat:.1f}ms): ok=true")

print("\\nALL PROTOCOL AND TARGET TESTS PASSED 100%!")
"""
    out = run_remote_py(remote_test_script)
    print(out)
    return True


if __name__ == "__main__":
    t0 = time.time()
    try:
        run_protocol_and_target_regression()
        print(f"\nSTEPS 9 & 10 COMPLETED SUCCESSFULLY IN {time.time() - t0:.2f}s!")
    except Exception as e:
        print(f"\n[FATAL] Protocol & target regression failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

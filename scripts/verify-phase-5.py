#!/usr/bin/env python3
"""E2E Verification Suite for Phase 5: Controlled Writes on MCP-Pi."""

import json
import os
import sys
import time
import urllib.request
import urllib.error

# Setup PYTHONPATH to import mcp_gateway
sys.path.insert(0, "/home/mcp-gateway/mcp-gateway/src")

from mcp_gateway.registry import SQLiteRegistry
from mcp_gateway.ssh_transport import SSHTransport
from mcp_gateway.tools import GatewayTools

DB_PATH = "/home/mcp-gateway/.local/share/mcp-gateway/gateway.db"
HTTP_URL = "http://127.0.0.1:8090/mcp"
ADAPTER_BIN = "/home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter"


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
    print("==================================================================")
    print("=== MCP PI PHASE 5: CONTROLLED WRITES END-TO-END VERIFICATION  ===")
    print("==================================================================\n")

    registry = SQLiteRegistry(DB_PATH)
    transport = SSHTransport()
    tools = GatewayTools(registry=registry, transport=transport)

    test_target = "termux-main"
    test_project = "write_smoke"

    # Verify project setup
    try:
        p = registry.get_project(test_target, test_project)
        print(f"[SETUP] Target '{test_target}' Project '{test_project}' root: {p['root']}")
        target_cfg = registry.get_target(test_target)
        transport.run_command(target_cfg, f"rm -f '{p['root']}/fresh_file.txt' '{p['root']}/mcp_created.txt'")
    except Exception as e:
        print(f"[FATAL] Project '{test_project}' not found in registry: {e}")
        sys.exit(1)

    # 1. MCP Tool Discovery
    print("\n--- 1. MCP TOOL DISCOVERY (9 TOOLS) ---")
    list_req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    resp, lat = send_http_mcp(list_req)
    tools_list = [t["name"] for t in resp.get("result", {}).get("tools", [])]
    print(f"Discovered {len(tools_list)} tools in {lat:.1f}ms: {tools_list}")
    assert "write_file" in tools_list, "write_file tool not discovered!"
    assert len(tools_list) == 9, f"Expected 9 tools, got {len(tools_list)}"
    print("PASS: 9 tools verified in MCP protocol discovery.")

    # 2. Baseline Health Check
    print("\n--- 2. BASELINE HEALTH CHECK ---")
    h = tools.health()
    h_res = h.get("result", {})
    print(f"Health: ok={h.get('ok')}, writes_enabled={h_res.get('writes_enabled')}")
    assert "writes_enabled" in h_res, "writes_enabled missing in health output"
    print("PASS: Health reports writes_enabled parameter.")

    # Reset initial state: writes_enabled=false, write_smoke.write=false
    registry.set_setting("writes_enabled", "false")
    proj_data = dict(p)
    proj_data["write"] = False
    registry.update_project(test_target, test_project, proj_data)

    # 3. Negative Vector: Global Writes Disabled
    print("\n--- 3. NEGATIVE: GLOBAL WRITES DISABLED ---")
    res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="existing.txt",
        content="should fail\n",
        dry_run=False,
    )
    print(f"Result: ok={res.get('ok')}, error={res.get('error')}")
    assert not res.get("ok"), "Expected write to fail when writes_enabled=false"
    assert res.get("error", {}).get("code") == "WRITES_DISABLED", f"Expected WRITES_DISABLED, got {res}"
    print("PASS: Global writes_enabled=false strictly blocks mutation with WRITES_DISABLED.")

    # 4. Negative Vector: Project Write Disabled
    print("\n--- 4. NEGATIVE: PROJECT WRITE CAPABILITY DISABLED ---")
    registry.set_setting("writes_enabled", "true")
    res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="existing.txt",
        content="should fail\n",
        dry_run=False,
    )
    print(f"Result: ok={res.get('ok')}, error={res.get('error')}")
    assert not res.get("ok"), "Expected write to fail when project.write=false"
    assert res.get("error", {}).get("code") == "WRITE_NOT_ALLOWED", f"Expected WRITE_NOT_ALLOWED, got {res}"
    print("PASS: project.write=false strictly blocks mutation with WRITE_NOT_ALLOWED.")

    # Enable write capability on project
    proj_data["write"] = True
    registry.update_project(test_target, test_project, proj_data)
    print("[SETUP] Enabled project.write=True on write_smoke.")

    # 5. Read Existing File Baseline & SHA256
    print("\n--- 5. READ FILE BASELINE (SHA256) ---")
    read_res = tools.read_file(target=test_target, project=test_project, relative_path="existing.txt")
    assert read_res.get("ok"), f"read_file failed: {read_res}"
    orig_sha = read_res["result"].get("sha256")
    orig_content = read_res["result"].get("content")
    print(f"Read existing.txt: {len(orig_content)} bytes, sha256={orig_sha}")
    assert orig_sha, "read_file must return sha256"
    assert orig_content == "hello world\n", f"Unexpected content: {orig_content}"
    print("PASS: read_file includes correct sha256 hash.")

    # 6. Dry Run Verification
    print("\n--- 6. POSITIVE: DRY RUN (NO MUTATION) ---")
    dry_res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="existing.txt",
        content="hello world modified dry run\n",
        expected_sha256=orig_sha,
        dry_run=True,
    )
    dry_res_data = dry_res.get("result", {})
    print(f"Dry run result: ok={dry_res.get('ok')}, dry_run={dry_res_data.get('dry_run')}")
    assert dry_res.get("ok") and dry_res_data.get("dry_run"), f"Dry run failed: {dry_res}"
    assert "diff" in dry_res_data, "Dry run must return diff"
    print(f"Diff output:\n{dry_res_data.get('diff')}")
    # Verify file was NOT modified
    verify_read = tools.read_file(target=test_target, project=test_project, relative_path="existing.txt")
    assert verify_read["result"].get("content") == orig_content, "File was modified during dry_run!"
    assert verify_read["result"].get("sha256") == orig_sha, "File hash changed during dry_run!"
    print("PASS: Dry run returned unified diff without modifying target file.")

    # 7. Negative Vector: Write Conflict (Hash Mismatch)
    print("\n--- 7. NEGATIVE: WRITE CONFLICT (HASH MISMATCH) ---")
    conflict_res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="existing.txt",
        content="conflict content\n",
        expected_sha256="0000000000000000000000000000000000000000000000000000000000000000",
        dry_run=False,
    )
    print(f"Conflict result: ok={conflict_res.get('ok')}, error={conflict_res.get('error')}")
    assert not conflict_res.get("ok"), "Expected write conflict"
    assert conflict_res.get("error", {}).get("code") == "WRITE_CONFLICT", f"Expected WRITE_CONFLICT, got {conflict_res}"
    print("PASS: Hash mismatch strictly rejected with WRITE_CONFLICT (lost update prevented).")

    # 8. Positive: Real Atomic Overwrite with Correct Expected SHA256
    print("\n--- 8. POSITIVE: ATOMIC OVERWRITE WITH EXPECTED SHA256 ---")
    new_text = "hello world updated Phase 5 live\n"
    write_res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="existing.txt",
        content=new_text,
        expected_sha256=orig_sha,
        dry_run=False,
    )
    write_res_data = write_res.get("result", {})
    print(f"Write result: ok={write_res.get('ok')}, bytes_written={write_res_data.get('bytes_written')}, new_sha={write_res_data.get('sha256')}")
    assert write_res.get("ok"), f"Write failed: {write_res}"
    assert write_res_data.get("backup_path"), "Backup path must be reported"
    backup_path = write_res_data.get("backup_path")
    print(f"Backup created at: {backup_path}")

    # Verify content and sha on target
    post_read = tools.read_file(target=test_target, project=test_project, relative_path="existing.txt")
    assert post_read["result"].get("content") == new_text, f"Content mismatch: {post_read.get('content')}"
    assert post_read["result"].get("sha256") == write_res_data.get("sha256"), "SHA256 mismatch after write"
    print("PASS: Real atomic overwrite succeeded and hash verified.")

    # 9. Positive: Create New File
    print("\n--- 9. POSITIVE: CREATE NEW FILE (create=True) ---")
    create_text = "newly created file content\nline 2\n"
    create_res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="fresh_file.txt",
        content=create_text,
        create=True,
    )
    create_res_data = create_res.get("result", {})
    print(f"Create result: ok={create_res.get('ok')}, sha={create_res_data.get('sha256')}")
    assert create_res.get("ok"), f"Create failed: {create_res}"
    create_read = tools.read_file(target=test_target, project=test_project, relative_path="fresh_file.txt")
    assert create_read["result"].get("content") == create_text, "Content mismatch in fresh file"
    print("PASS: New file created successfully with create=True.")

    # 10. Negative: Create on Existing File
    print("\n--- 10. NEGATIVE: CREATE ON EXISTING FILE ---")
    dup_res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="fresh_file.txt",
        content="should fail\n",
        create=True,
    )
    print(f"Duplicate create result: ok={dup_res.get('ok')}, error={dup_res.get('error')}")
    assert not dup_res.get("ok")
    assert dup_res.get("error", {}).get("code") == "FILE_ALREADY_EXISTS"
    print("PASS: create=True on existing file rejected with FILE_ALREADY_EXISTS.")

    # 11. Negative: Overwrite Missing File
    print("\n--- 11. NEGATIVE: OVERWRITE NON-EXISTENT FILE ---")
    missing_res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="does_not_exist.txt",
        content="should fail\n",
        create=False,
    )
    print(f"Missing overwrite result: ok={missing_res.get('ok')}, error={missing_res.get('error')}")
    assert not missing_res.get("ok")
    assert missing_res.get("error", {}).get("code") == "NOT_FOUND"
    print("PASS: Overwrite on missing file rejected with NOT_FOUND.")

    # 12. Negative: Symlink Target Write Denied
    print("\n--- 12. NEGATIVE: SYMLINK TARGET WRITE DENIED ---")
    sym_res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="symlink-file.txt",
        content="malicious overwrite\n",
    )
    print(f"Symlink target result: ok={sym_res.get('ok')}, error={sym_res.get('error')}")
    assert not sym_res.get("ok")
    assert sym_res.get("error", {}).get("code") == "SYMLINK_WRITE_DENIED"
    print("PASS: Writing to symlink target strictly blocked with SYMLINK_WRITE_DENIED.")

    # 13. Negative: Symlink Directory / Escape Denied
    print("\n--- 13. NEGATIVE: SYMLINK DIR ESCAPE DENIED ---")
    symdir_res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="symlink-dir/subfile.txt",
        content="malicious escape\n",
    )
    print(f"Symlink dir result: ok={symdir_res.get('ok')}, error={symdir_res.get('error')}")
    assert not symdir_res.get("ok")
    assert symdir_res.get("error", {}).get("code") in ("SYMLINK_WRITE_DENIED", "INVALID_PATH")
    print("PASS: Writing through symlink directory strictly blocked.")

    # 14. Negative: Path Traversal Escape Denied
    print("\n--- 14. NEGATIVE: PATH TRAVERSAL ESCAPE DENIED ---")
    trav_res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="../escape_target.txt",
        content="escape\n",
    )
    print(f"Traversal result: ok={trav_res.get('ok')}, error={trav_res.get('error')}")
    assert not trav_res.get("ok")
    assert trav_res.get("error", {}).get("code") == "INVALID_PATH"
    print("PASS: Path traversal (..) strictly rejected with INVALID_PATH.")

    # 15. Negative: Oversized Content Denied
    print("\n--- 15. NEGATIVE: OVERSIZED WRITE DENIED ---")
    huge_content = "X" * 300000  # Default max is 262144 bytes
    huge_res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="huge.txt",
        content=huge_content,
        create=True,
    )
    print(f"Oversized result: ok={huge_res.get('ok')}, error={huge_res.get('error')}")
    assert not huge_res.get("ok")
    assert huge_res.get("error", {}).get("code") == "FILE_TOO_LARGE"
    print("PASS: Content exceeding max_write_bytes rejected with FILE_TOO_LARGE.")

    # 16. Negative: Invalid Encoding (NUL byte / Binary)
    print("\n--- 16. NEGATIVE: NUL BYTE / BINARY CONTENT DENIED ---")
    nul_res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="nul.txt",
        content="valid text\x00corrupt binary",
        create=True,
    )
    print(f"NUL byte result: ok={nul_res.get('ok')}, error={nul_res.get('error')}")
    assert not nul_res.get("ok")
    assert nul_res.get("error", {}).get("code") == "INVALID_ENCODING"
    print("PASS: NUL bytes / non-UTF8 rejected with INVALID_ENCODING.")

    # 17. MCP Protocol Over HTTP Calling write_file
    print("\n--- 17. MCP PROTOCOL CALL OVER STREAMABLE HTTP ---")
    mcp_call_req = {
        "jsonrpc": "2.0",
        "id": 100,
        "method": "tools/call",
        "params": {
            "name": "write_file",
            "arguments": {
                "target": test_target,
                "project": test_project,
                "relative_path": "mcp_created.txt",
                "content": "created via MCP Streamable HTTP protocol\n",
                "create": True,
            }
        }
    }
    mcp_resp, lat = send_http_mcp(mcp_call_req)
    print(f"MCP Response in {lat:.1f}ms: isError={mcp_resp.get('result', {}).get('isError')}")
    assert not mcp_resp.get("result", {}).get("isError"), f"MCP tool call returned error: {mcp_resp}"
    mcp_content_text = mcp_resp["result"]["content"][0]["text"]
    mcp_parsed = json.loads(mcp_content_text)
    assert mcp_parsed.get("ok"), f"MCP payload not ok: {mcp_parsed}"
    print(f"PASS: MCP write_file succeeded via Streamable HTTP (sha={mcp_parsed['result'].get('sha256')}).")

    # 18. Panic Button / Emergency Writes Disable
    print("\n--- 18. PANIC CONTROL: DISABLE WRITES (READS PRESERVED) ---")
    registry.set_setting("writes_enabled", "false")
    # Verify write is now blocked
    write_blocked = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="existing.txt",
        content="panic test\n",
    )
    assert not write_blocked.get("ok")
    assert write_blocked.get("error", {}).get("code") == "WRITES_DISABLED"
    print("Write successfully blocked under panic state with WRITES_DISABLED.")

    # Verify read continues to work
    read_still_works = tools.read_file(target=test_target, project=test_project, relative_path="existing.txt")
    assert read_still_works.get("ok"), "Read failed under panic state!"
    print(f"Read remains fully operational: {len(read_still_works['result'].get('content'))} bytes read.")
    print("PASS: Panic disable-writes switch isolates writes without impacting read operations.")

    # 19. Backup & Recovery Verification
    print("\n--- 19. BACKUP & RECOVERY VERIFICATION ---")
    # Backup was created in step 8
    print(f"Verifying backup at {backup_path}...")
    assert os.path.isfile(backup_path), f"Backup file {backup_path} does not exist!"
    with open(backup_path, "r", encoding="utf-8") as bf:
        backup_content = bf.read()
    assert backup_content == orig_content, "Backup content does not match original content!"
    print("PASS: Backup file verified with exact original content.")

    # Restore original content to existing.txt on target worker
    print("Restoring existing.txt to original baseline state...")
    registry.set_setting("writes_enabled", "true")
    current_read = tools.read_file(target=test_target, project=test_project, relative_path="existing.txt")
    restore_res = tools.write_file(
        target=test_target,
        project=test_project,
        relative_path="existing.txt",
        content=backup_content,
        expected_sha256=current_read["result"].get("sha256"),
    )
    assert restore_res.get("ok"), f"Restore write failed: {restore_res}"
    restored_read = tools.read_file(target=test_target, project=test_project, relative_path="existing.txt")
    assert restored_read["result"].get("content") == "hello world\n"
    assert restored_read["result"].get("sha256") == orig_sha
    print(f"PASS: existing.txt cleanly restored to original SHA256 ({orig_sha}).")

    # Cleanup created test files on target worker
    print("\n--- CLEANUP TEMPORARY FILES ---")
    target_cfg = registry.get_target(test_target)
    transport.run_command(target_cfg, f"rm -f '{p['root']}/fresh_file.txt' '{p['root']}/mcp_created.txt'")
    # Reset registry to safe default
    registry.set_setting("writes_enabled", "false")
    proj_data["write"] = False
    registry.update_project(test_target, test_project, proj_data)
    print("Registry settings reset to safe defaults (writes_enabled=false, project.write=false).")

    print("\n==================================================================")
    print("=== ALL 19/19 VERIFICATION TESTS PASSED SUCCESSFULLY!          ===")
    print("==================================================================")


if __name__ == "__main__":
    main()

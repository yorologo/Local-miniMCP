# Full Operational Control for MCP_Local Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement full operational control and Termux environment administration for `chatgpt-main` on project `MCP_Local`, including the new `run_command` shell execution tool and the complete suite of strictly confined filesystem tools (`append_file`, `delete_file`, `copy_file`, `move_file`, `mkdir`, `search`).

**Architecture:** Extend Gateway Core in Python (`policy.py`, `tools.py`, `bridge.py`, `ssh_transport.py`) and the Go MCP Adapter (`server.go`) to expose and authorize `run_command` and filesystem tools. Delegate execution via SSH to Target Worker `termux-main` under full Termux shell and environment propagation (`HOME`, `PREFIX`, `PATH`, `TMPDIR`, `LANG`), keeping filesystem tools confined to `MCP_Local` while permitting official package and environment managers (`pkg`, `apt`, `pip`, `npm`) to maintain the runtime.

**Tech Stack:** Python 3.9+, Go 1.27 (ARMv6 cross-compilation), Bash / POSIX Shell, SQLite 3, Linux systemd.

**Spec:** `docs/superpowers/specs/2026-09-14-full-operational-control-mcp-local-design.md`

## Global Constraints
- Confinement: Direct filesystem tools must strictly resolve within `/data/data/com.termux/files/home/Projects/test/MCP_Local`. Traversal (`..`) and symlink escapes must fail closed.
- Execution: `run_command` must default `cwd` to `MCP_Local`, support full shell syntax (`&&`, `||`, `;`, `|`, `<`, `<<`, `>`, `>>`, `$()`, variables, subshells), and preserve Termux environment variables (`HOME`, `PREFIX`, `PATH`, `TMPDIR`, `LANG`, `TERMUX_VERSION`).
- Decoupling: CWD confinement must not prevent execution of system binaries in `$PREFIX/bin` (`git`, `python`, `pkg`, `apt`, `npm`, `clang`, `pytest`).
- Permissions: No root, no exploits, no SELinux disabling.
- Capability: `*` authorizes all operations including `environment_management`.
- Invariants: Emergency Kill Switch and project write toggles must remain functional. No destructive commands on existing work.

---

### Task 1: Policy Engine & Capability Hierarchy Enhancement

**Files:**
- Modify: `src/mcp_gateway/policy.py:155-250`
- Test: `tests/test_policy.py`

**Interfaces:**
- Consumes: Existing `TOOL_CAPABILITIES`, `authorize_client`
- Produces: Expanded `TOOL_CAPABILITIES` mapping for `run_command`, `append_file`, `delete_file`, `copy_file`, `move_file`, `mkdir`, `search` with capabilities `write`, `execute`, `environment_management`, and `*`.

- [ ] **Step 1: Write failing unit test in `tests/test_policy.py`**

```python
    def test_run_command_and_extended_fs_capabilities(self):
        reg = InMemoryRegistry({
            "clients": [{"id": "c_all", "enabled": True}, {"id": "c_ro", "enabled": True}],
            "grants": [
                {"client_id": "c_all", "target_id": "t1", "project_id": "p1", "capability": "*", "enabled": True},
                {"client_id": "c_ro", "target_id": "t1", "project_id": "p1", "capability": "read", "enabled": True},
            ],
            "targets": [{"id": "t1", "enabled": True}],
            "projects": [{"id": "p1", "target_id": "t1", "enabled": True, "read": True, "write": True}],
            "settings": {"gateway_enabled": "true", "writes_enabled": "true"}
        })
        for tool in ["run_command", "append_file", "delete_file", "copy_file", "move_file", "mkdir", "search"]:
            auth_ok, _ = authorize_client("c_all", "t1", "p1", tool, reg)
            self.assertTrue(auth_ok, f"{tool} should be authorized for c_all with *")
            
        auth_no, err = authorize_client("c_ro", "t1", "p1", "run_command", reg)
        self.assertFalse(auth_no)
        self.assertIn("TOOL_NOT_ALLOWED", err)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m unittest tests/test_policy.py`  
Expected: FAIL with `Tool 'run_command' not in gateway catalog`

- [ ] **Step 3: Update `src/mcp_gateway/policy.py`**

Add tool mappings to `TOOL_CAPABILITIES`:
```python
    "run_command": {"execute", "run_command", "environment_management", "*"},
    "append_file": {"write", "append_file", "*"},
    "delete_file": {"write", "delete_file", "*"},
    "copy_file": {"write", "copy_file", "*"},
    "move_file": {"write", "move_file", "*"},
    "mkdir": {"write", "mkdir", "*"},
    "search": {"read", "search", "*"},
```
Ensure `authorize_client` treats `environment_management` as part of `*` and evaluates write policy for mutating tools.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python3 -m unittest tests/test_policy.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_gateway/policy.py tests/test_policy.py
git commit -m "feat(policy): expand capability catalog for run_command and extended filesystem tools"
```

---

### Task 2: SSH Transport Target Shell Execution Support

**Files:**
- Modify: `src/mcp_gateway/ssh_transport.py:100-250`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: Target SSH configuration (`user`, `host`, `port`, `key_path`)
- Produces: `execute_shell(self, target_cfg, command, cwd, env, timeout, stdin_data)` returning `{"stdout": str, "stderr": str, "exit_code": int, "timed_out": bool, "duration": float, "effective_cwd": str}`

- [ ] **Step 1: Write unit test verifying shell execution and environment handling**

Add test in `tests/test_tools.py` mocking or invoking transport shell execution with `effective_cwd` and environment retention.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m unittest tests/test_tools.py`  
Expected: FAIL with attribute error on `execute_shell`

- [ ] **Step 3: Implement `execute_shell` in `src/mcp_gateway/ssh_transport.py`**

Implement `execute_shell`:
- Preserve and inject standard Termux environment variables (`HOME`, `PREFIX`, `PATH`, `TMPDIR`, `LANG`, `TERMUX_VERSION`).
- Escape and construct remote wrapper:
  `cd <cwd> && $SHELL -c <command>`
- Measure duration using `time.monotonic()`.
- Capture `stdout`, `stderr`, returncode, and handle `subprocess.TimeoutExpired`.

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH=src python3 -m unittest tests/test_tools.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_gateway/ssh_transport.py tests/test_tools.py
git commit -m "feat(transport): add execute_shell with Termux environment propagation and timeout tracking"
```

---

### Task 3: Gateway Core Filesystem & Execution Tools

**Files:**
- Modify: `src/mcp_gateway/tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: `SSHTransport.execute_shell`, `validate_path`, `validate_canonical_path`
- Produces: `run_command`, `append_file`, `delete_file`, `copy_file`, `move_file`, `mkdir`, `search` methods on `GatewayTools`.

- [ ] **Step 1: Write unit tests in `tests/test_tools.py`**

Test:
- `run_command` defaults `cwd` to project root and validates output structure.
- `append_file` writes to end of file and enforces `max_write_bytes`.
- `delete_file` removes file and rejects project root deletion.
- `copy_file` and `move_file` validate both source and destination within project root.
- `mkdir` creates directory within project root.
- `search` finds text/pattern within project root.

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=src python3 -m unittest tests/test_tools.py`  
Expected: FAIL with missing methods on `GatewayTools`

- [ ] **Step 3: Implement methods in `src/mcp_gateway/tools.py`**

Implement all 7 methods with strict root confinement checks, error codes (`INVALID_PATH`, `WRITE_NOT_ALLOWED`, `WRITES_DISABLED`), and audit logging.

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH=src python3 -m unittest tests/test_tools.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_gateway/tools.py tests/test_tools.py
git commit -m "feat(tools): implement run_command and extended filesystem tools in Gateway Core"
```

---

### Task 4: Python Bridge Serialization & CLI

**Files:**
- Modify: `src/mcp_gateway/bridge.py`
- Test: `tests/test_bridge.py`

**Interfaces:**
- Consumes: `GatewayTools` methods
- Produces: CLI commands for all new tools via `python3 -m mcp_gateway.bridge invoke --tool <name> ...`

- [ ] **Step 1: Write unit tests in `tests/test_bridge.py`**

Verify CLI parsing and JSON invocation for `run_command` and new filesystem tools.

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=src python3 -m unittest tests/test_bridge.py`  
Expected: FAIL with unrecognized tool choice

- [ ] **Step 3: Implement bridge CLI handlers in `src/mcp_gateway/bridge.py`**

Add tools to `SUPPORTED_TOOLS` and wire up argument extraction and gateway invocation.

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH=src python3 -m unittest tests/test_bridge.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_gateway/bridge.py tests/test_bridge.py
git commit -m "feat(bridge): add CLI and serialization handlers for run_command and extended tools"
```

---

### Task 5: Go MCP Adapter Catalog, Schemas & ARMv6 Build

**Files:**
- Modify: `mcp-adapter/server.go`
- Modify: `mcp-adapter/server_test.go`
- Binary: `mcp-adapter/mcp-gateway-adapter`

**Interfaces:**
- Consumes: MCP protocol specification (2026-07-28), Python bridge CLI
- Produces: Go MCP Adapter binary with schemas for all 21 tools.

- [ ] **Step 1: Add tools and schemas to `mcp-adapter/server.go`**

- Add new tools to `allKnownTools`.
- Implement `registerToolByName` cases with full JSON schemas matching specifications.
- Implement argument extraction in tool handlers.

- [ ] **Step 2: Update `mcp-adapter/server_test.go`**

Ensure test fixtures configure appropriate client grants and test tool discovery.

- [ ] **Step 3: Build ARMv6 binary**

Run: `./scripts/build-armv6.sh bin/mcp-gateway-adapter-linux-armv6`  
Verify checksum and file size.

- [ ] **Step 4: Commit**

```bash
git add mcp-adapter/server.go mcp-adapter/server_test.go bin/mcp-gateway-adapter-linux-armv6
git commit -m "feat(adapter): add run_command and extended filesystem tools to Go MCP Adapter"
```

---

### Task 6: Appliance Deployment & Service Autostart

**Files:**
- Remote deployment to Raspberry Pi `192.168.68.55`

- [ ] **Step 1: Deploy updated Python Core to Raspberry Pi**

Sync `src/mcp_gateway/` to `/home/mcp-gateway/mcp-gateway/src/`.

- [ ] **Step 2: Deploy compiled Go Adapter binary to Raspberry Pi**

Copy `bin/mcp-gateway-adapter-linux-armv6` to `/home/mcp-gateway/mcp-gateway/bin/` and set executable permissions.

- [ ] **Step 3: Restart systemd daemons**

Restart `mcp-gateway-mcp.service` and verify `active (running)`.

- [ ] **Step 4: Run unified Doctor on Raspberry Pi**

Run `bin/mcp-gateway doctor` on the Pi and verify 19/19 checks PASS.

---

### Task 7: Comprehensive End-to-End Validation Suite

**Files:**
- Test scripts and validation checks

- [ ] **Step 1: Validate Project Scope via MCP**
  - Verify `pwd` starts in `/data/data/com.termux/files/home/Projects/test/MCP_Local`.
  - Create `.mcp_scope_test` via `write_file`.
  - Read `.mcp_scope_test` via `read_file`.
  - Append to `.mcp_scope_test` via `append_file`.
  - Delete `.mcp_scope_test` via `delete_file`.
  - Verify rejection of `..` traversal escape attempts.

- [ ] **Step 2: Validate Shell Execution**
  - Run `python -c "print('MCP_EXEC_OK')"` via `run_command`.
  - Verify `exit_code: 0`, `stdout: "MCP_EXEC_OK\n"`.

- [ ] **Step 3: Validate Full Git Workflow**
  - Create temporary file `tmp_git_probe.txt`.
  - Run `git add tmp_git_probe.txt` via `run_command`.
  - Run `git status --short` and verify staged file.
  - Run `git rm -f tmp_git_probe.txt` to restore clean state without altering existing unstaged files.

- [ ] **Step 4: Validate Package Management**
  - Run non-destructive inspection: `pkg --version`, `apt --version`, `python -m pip --version`, `npm --version`.
  - Verify policy engine authorizes package installation commands for `chatgpt-main` with capability `*`.

- [ ] **Step 5: Validate Emergency Kill Switch & Panic Button**
  - Test disabling writes via setting/API and verify write commands fail with `WRITES_DISABLED`.
  - Re-enable writes and verify normal operation restored.

- [ ] **Step 6: Notify and Final Report**
  - Send notification via `$HOME/bin/ai-notify done`.
  - Present final summary matching user requirement 25.

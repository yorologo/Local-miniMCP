"""Standard tools implementation for MCP Gateway."""

import difflib
import hashlib
import json
import os
import platform
import shlex
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from typing import Any, Dict, Optional

from . import __version__
from .config import ConfigError, GatewayConfig
from .policy import (
    PolicyError,
    can_client_use_tool,
    check_capability,
    validate_canonical_path,
    validate_content_utf8,
    validate_relative_path,
    validate_task,
    validate_write_relative_path,
    validate_write_size,
)
from .ssh_transport import SSHError, SSHTransport
from .discovery import TargetDiscovery


class GatewayTools:
    """Provides high-level, audited operations on configured targets."""

    def __init__(
        self,
        config: Optional[GatewayConfig] = None,
        transport: Optional[SSHTransport] = None,
        registry: Optional[Any] = None,
        request_id: Optional[str] = None,
        client_id: Optional[str] = None,
    ):
        self.config = registry or config or GatewayConfig.load()
        if transport:
            self.transport = transport
            if getattr(self.transport, "registry", None) is None:
                self.transport.registry = self.config
        else:
            self.transport = SSHTransport(
                discovery=TargetDiscovery(),
                registry=self.config,
            )
        self.request_id = request_id
        self.client_id = client_id or "local"

    def _success_response(
        self,
        tool: str,
        result: Dict[str, Any],
        target: Optional[str] = None,
        project: Optional[str] = None,
        start_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        duration_ms = int((time.monotonic() - (start_time or time.monotonic())) * 1000)
        resp: Dict[str, Any] = {
            "ok": True,
            "tool": tool,
            "duration_ms": duration_ms,
            "result": result,
        }
        if self.request_id:
            resp["request_id"] = self.request_id
        if target:
            resp["target"] = target
        if project:
            resp["project"] = project
        return resp

    def _error_response(
        self,
        tool: str,
        code: str,
        message: str,
        target: Optional[str] = None,
        project: Optional[str] = None,
        start_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        duration_ms = int((time.monotonic() - (start_time or time.monotonic())) * 1000)
        resp: Dict[str, Any] = {
            "ok": False,
            "tool": tool,
            "duration_ms": duration_ms,
            "error": {
                "code": code,
                "message": message,
            },
        }
        if self.request_id:
            resp["request_id"] = self.request_id
        if target:
            resp["target"] = target
        if project:
            resp["project"] = project
        return resp

    def _is_gateway_enabled(self) -> bool:
        if hasattr(self.config, "get_setting"):
            val = self.config.get_setting("gateway_enabled", "true")
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                return val.lower() in ("true", "1", "yes", "on")
            if val is not None:
                return bool(val)
        return True

    def _is_writes_enabled(self) -> bool:
        if hasattr(self.config, "get_setting"):
            val = self.config.get_setting("writes_enabled", "false")
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                return val.lower() in ("true", "1", "yes", "on")
            if val is not None:
                return bool(val)
        return False

    def _get_setting(self, key: str, default: Any = None) -> Any:
        if hasattr(self.config, "get_setting"):
            return self.config.get_setting(key, default)
        return default

    def _record_audit(
        self,
        action: str,
        target_id: Optional[str] = None,
        project_id: Optional[str] = None,
        start_time: Optional[float] = None,
        success: int = 1,
        error_code: Optional[str] = None,
        bytes_transferred: Optional[int] = None,
        detail: Optional[Any] = None,
    ) -> None:
        if hasattr(self.config, "record_activity"):
            duration_ms = int((time.monotonic() - (start_time or time.monotonic())) * 1000)
            detail_dict = {}
            if isinstance(detail, dict):
                detail_dict = dict(detail)
            elif detail:
                detail_dict["detail"] = str(detail)
            if self.request_id:
                detail_dict["request_id"] = self.request_id
            detail_str = json.dumps(detail_dict) if detail_dict else ""
            try:
                self.config.record_activity({
                    "actor": self.client_id or "mcp-local",
                    "action": action,
                    "target_id": target_id,
                    "project_id": project_id,
                    "duration_ms": duration_ms,
                    "success": success,
                    "error_code": error_code,
                    "bytes_transferred": bytes_transferred,
                    "detail": detail_str,
                })
            except Exception:
                pass

    def _check_gateway_enabled(
        self, tool: str, target: Optional[str] = None, project: Optional[str] = None, start_time: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        if not self._is_gateway_enabled():
            return self._error_response(
                tool=tool,
                code="GATEWAY_DISABLED",
                message="Gateway operations are disabled by administrator kill switch",
                target=target,
                project=project,
                start_time=start_time,
            )
        can_use, deny_reason = can_client_use_tool(self.client_id, tool, self.config)
        if not can_use:
            return self._error_response(
                tool=tool,
                code="CLIENT_UNAUTHORIZED",
                message=deny_reason or "Client is not authorized to use this tool",
                target=target,
                project=project,
                start_time=start_time,
            )
        return None

    def health(self) -> Dict[str, Any]:
        """Return gateway status and system metadata."""
        start_time = time.monotonic()
        try:
            is_enabled = self._is_gateway_enabled()
            writes_enabled = self._is_writes_enabled()
            res = {
                "gateway_status": "ok" if is_enabled else "disabled",
                "gateway_enabled": is_enabled,
                "writes_enabled": writes_enabled,
                "hostname": socket.gethostname(),
                "gateway_version": __version__,
                "architecture": platform.machine(),
                "python_version": platform.python_version(),
                "config_loaded": bool(self.config),
                "configured_targets": self.config.target_count,
            }
            return self._success_response("health", res, start_time=start_time)
        except Exception as e:
            return self._error_response("health", "INTERNAL_ERROR", str(e), start_time=start_time)

    def list_targets(self) -> Dict[str, Any]:
        """Return safe list of configured targets without secrets."""
        start_time = time.monotonic()
        try:
            targets = self.config.list_targets()
            return self._success_response("list_targets", {"targets": targets}, start_time=start_time)
        except Exception as e:
            return self._error_response("list_targets", "INTERNAL_ERROR", str(e), start_time=start_time)

    def target_status(self, target: str) -> Dict[str, Any]:
        """Verify reachability and latency of a target."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("target_status", target=target, start_time=start_time)
        if gw_check:
            return gw_check
        try:
            target_cfg = self.config.get_target(target)
            res = self.transport.run_command(target_cfg, "hostname", timeout=10, request_id=self.request_id)
            if not res.ok:
                return self._error_response(
                    "target_status",
                    "SSH_FAILED",
                    f"Remote status check failed: {res.stderr.strip()}",
                    target=target,
                    start_time=start_time,
                )
            result = {
                "reachable": True,
                "remote_hostname": res.stdout.strip(),
                "latency_ms": res.duration_ms,
                "platform": target_cfg.get("platform"),
            }
            return self._success_response("target_status", result, target=target, start_time=start_time)
        except (ConfigError, PolicyError) as e:
            return self._error_response("target_status", e.code, str(e), target=target, start_time=start_time)
        except SSHError as e:
            return self._error_response("target_status", e.code, str(e), target=target, start_time=start_time)

    def _resolve_and_validate_path(
        self, target_cfg: Dict[str, Any], project_cfg: Dict[str, Any], relative_path: str
    ) -> str:
        """Helper to validate syntax, construct candidate path, and canonicalize remotely."""
        clean_rel = validate_relative_path(relative_path)
        root = project_cfg["root"]

        if clean_rel == ".":
            candidate = root
        else:
            candidate = f"{root}/{clean_rel}"

        canonical = self.transport.resolve_canonical_path(target_cfg, candidate)
        validate_canonical_path(canonical, root)
        return canonical

    def list_directory(
        self, target: str, project: str, relative_path: str = "."
    ) -> Dict[str, Any]:
        """List directory contents within an allowed project root (max 200 entries)."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("list_directory", target=target, project=project, start_time=start_time)
        if gw_check:
            return gw_check
        try:
            target_cfg = self.config.get_target(target)
            project_cfg = self.config.get_project(target, project)
            check_capability(project_cfg, "read")

            canonical = self._resolve_and_validate_path(target_cfg, project_cfg, relative_path)

            py_code = (
                "import os, sys, json\n"
                "p = sys.argv[1]\n"
                "if not os.path.exists(p):\n"
                "    sys.exit(2)\n"
                "if not os.path.isdir(p):\n"
                "    sys.exit(3)\n"
                "entries = []\n"
                "try:\n"
                "    for name in sorted(os.listdir(p))[:200]:\n"
                "        fp = os.path.join(p, name)\n"
                "        t = 'symlink' if os.path.islink(fp) else ('directory' if os.path.isdir(fp) else ('file' if os.path.isfile(fp) else 'other'))\n"
                "        s = os.path.getsize(fp) if t == 'file' else None\n"
                "        entries.append({'name': name, 'type': t, 'size': s})\n"
                "    print(json.dumps(entries))\n"
                "except Exception as e:\n"
                "    print(str(e), file=sys.stderr)\n"
                "    sys.exit(4)\n"
            )

            cmd = f"python3 -c {shlex.quote(py_code)} {shlex.quote(canonical)}"
            res = self.transport.run_command(target_cfg, cmd, timeout=15, request_id=self.request_id)

            if res.exit_code == 2:
                return self._error_response("list_directory", "NOT_FOUND", f"Directory not found: {relative_path}", target, project, start_time)
            if res.exit_code == 3:
                return self._error_response("list_directory", "INVALID_PATH", f"Path is not a directory: {relative_path}", target, project, start_time)
            if not res.ok:
                return self._error_response("list_directory", "SSH_FAILED", res.stderr.strip() or "Failed to list directory", target, project, start_time)

            entries = json.loads(res.stdout.strip())
            result = {
                "relative_path": relative_path,
                "canonical_path": canonical,
                "count": len(entries),
                "entries": entries,
            }
            return self._success_response("list_directory", result, target, project, start_time)

        except (ConfigError, PolicyError) as e:
            return self._error_response("list_directory", e.code, str(e), target, project, start_time)
        except SSHError as e:
            return self._error_response("list_directory", e.code, str(e), target, project, start_time)

    def file_stat(
        self, target: str, project: str, relative_path: str
    ) -> Dict[str, Any]:
        """Obtain metadata of a file or directory inside project root."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("file_stat", target=target, project=project, start_time=start_time)
        if gw_check:
            return gw_check
        try:
            target_cfg = self.config.get_target(target)
            project_cfg = self.config.get_project(target, project)
            check_capability(project_cfg, "read")

            canonical = self._resolve_and_validate_path(target_cfg, project_cfg, relative_path)

            py_code = (
                "import os, sys, json\n"
                "p = sys.argv[1]\n"
                "if not os.path.exists(p):\n"
                "    sys.exit(2)\n"
                "st = os.stat(p)\n"
                "t = 'symlink' if os.path.islink(p) else ('directory' if os.path.isdir(p) else ('file' if os.path.isfile(p) else 'other'))\n"
                "print(json.dumps({'exists': True, 'type': t, 'size': st.st_size, 'mtime': int(st.st_mtime)}))\n"
            )

            cmd = f"python3 -c {shlex.quote(py_code)} {shlex.quote(canonical)}"
            res = self.transport.run_command(target_cfg, cmd, timeout=10, request_id=self.request_id)

            if res.exit_code == 2:
                return self._error_response("file_stat", "NOT_FOUND", f"File not found: {relative_path}", target, project, start_time)
            if not res.ok:
                return self._error_response("file_stat", "SSH_FAILED", res.stderr.strip() or "Stat failed", target, project, start_time)

            stat_data = json.loads(res.stdout.strip())
            stat_data["relative_path"] = relative_path
            stat_data["canonical_path"] = canonical
            return self._success_response("file_stat", stat_data, target, project, start_time)

        except (ConfigError, PolicyError) as e:
            return self._error_response("file_stat", e.code, str(e), target, project, start_time)
        except SSHError as e:
            return self._error_response("file_stat", e.code, str(e), target, project, start_time)

    def read_file(
        self, target: str, project: str, relative_path: str
    ) -> Dict[str, Any]:
        """Read text content of a file within project root with 1 MiB limit."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("read_file", target=target, project=project, start_time=start_time)
        if gw_check:
            return gw_check
        try:
            target_cfg = self.config.get_target(target)
            project_cfg = self.config.get_project(target, project)
            check_capability(project_cfg, "read")

            canonical = self._resolve_and_validate_path(target_cfg, project_cfg, relative_path)
            content = self.transport.read_remote_file_content(target_cfg, canonical)
            sha256_hex = hashlib.sha256(content.encode("utf-8")).hexdigest()

            result = {
                "relative_path": relative_path,
                "canonical_path": canonical,
                "size_bytes": len(content.encode("utf-8")),
                "content": content,
                "sha256": sha256_hex,
            }
            return self._success_response("read_file", result, target, project, start_time)

        except (ConfigError, PolicyError) as e:
            return self._error_response("read_file", e.code, str(e), target, project, start_time)
        except SSHError as e:
            return self._error_response("read_file", e.code, str(e), target, project, start_time)

    def git_status(self, target: str, project: str) -> Dict[str, Any]:
        """Execute 'git status --short' inside the project root."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("git_status", target=target, project=project, start_time=start_time)
        if gw_check:
            return gw_check
        try:
            target_cfg = self.config.get_target(target)
            project_cfg = self.config.get_project(target, project)
            root = project_cfg["root"]

            # Validate root exists remotely
            canonical = self.transport.resolve_canonical_path(target_cfg, root)
            validate_canonical_path(canonical, root)

            res = self.transport.run_command(target_cfg, "git status --short", cwd=canonical, timeout=20, request_id=self.request_id)
            if not res.ok:
                return self._error_response(
                    "git_status",
                    "SSH_FAILED",
                    f"git status failed: {res.stderr.strip()}",
                    target,
                    project,
                    start_time,
                )

            result = {
                "status_output": res.stdout.strip(),
            }
            return self._success_response("git_status", result, target, project, start_time)

        except (ConfigError, PolicyError) as e:
            return self._error_response("git_status", e.code, str(e), target, project, start_time)
        except SSHError as e:
            return self._error_response("git_status", e.code, str(e), target, project, start_time)

    def run_task(self, target: str, project: str, task: str) -> Dict[str, Any]:
        """Execute an allowlisted predefined task for a project."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("run_task", target=target, project=project, start_time=start_time)
        if gw_check:
            return gw_check
        try:
            target_cfg = self.config.get_target(target)
            project_cfg = self.config.get_project(target, project)
            task_def = validate_task(project_cfg, task)

            root = project_cfg["root"]
            canonical = self.transport.resolve_canonical_path(target_cfg, root)
            validate_canonical_path(canonical, root)

            argv = task_def["argv"]
            quoted_cmd = " ".join(shlex.quote(arg) for arg in argv)
            res = self.transport.run_command(
                target_cfg, quoted_cmd, cwd=canonical, timeout=task_def["timeout"], request_id=self.request_id
            )

            result = {
                "task": task,
                "exit_code": res.exit_code,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "duration_ms": res.duration_ms,
            }
            return self._success_response("run_task", result, target, project, start_time)

        except (ConfigError, PolicyError) as e:
            return self._error_response("run_task", e.code, str(e), target, project, start_time)
        except SSHError as e:
            return self._error_response("run_task", e.code, str(e), target, project, start_time)

    def write_file(
        self,
        target: str,
        project: str,
        relative_path: str,
        content: str,
        expected_sha256: Optional[str] = None,
        dry_run: bool = False,
        create: bool = False,
    ) -> Dict[str, Any]:
        """Atomically create or overwrite a text file in the project workspace with strict verification."""
        start_time = time.monotonic()

        # 1. Global kill switch check
        gw_check = self._check_gateway_enabled("write_file", target=target, project=project, start_time=start_time)
        if gw_check:
            self._record_audit(
                action="DENY", target_id=target, project_id=project,
                start_time=start_time, success=0, error_code="GATEWAY_DISABLED",
                detail={"path": relative_path, "tool": "write_file"}
            )
            return gw_check

        # 2. Global writes_enabled switch check
        if not self._is_writes_enabled():
            self._record_audit(
                action="DENY", target_id=target, project_id=project,
                start_time=start_time, success=0, error_code="WRITES_DISABLED",
                detail={"path": relative_path, "tool": "write_file"}
            )
            return self._error_response(
                "write_file", "WRITES_DISABLED",
                "Controlled writes are disabled by administrator setting",
                target, project, start_time
            )

        try:
            # 3. Target enabled check
            target_cfg = self.config.get_target(target)

            # 4. Project enabled check
            project_cfg = self.config.get_project(target, project)

            # 5. Project write capability check
            check_capability(project_cfg, "write")

            # 6. Validate content encoding & size limit
            content_bytes = validate_content_utf8(content)
            max_write_bytes = int(self._get_setting("max_write_bytes", 262144))
            validate_write_size(content_bytes, max_write_bytes)

            # 7. Validate path syntax (strictly relative, not root, no traversal)
            norm_rel_path = validate_write_relative_path(relative_path)

            # 8. Target write adapter capability check
            write_adapter = target_cfg.get("write_adapter", "posix-python")
            if write_adapter != "posix-python":
                raise PolicyError(
                    f"Target does not support write adapter: {write_adapter}",
                    code="WRITE_UNSUPPORTED_ON_TARGET"
                )

            # 9. Resolve project canonical root
            root = project_cfg["root"]
            root_canonical = self.transport.resolve_canonical_path(target_cfg, root)
            validate_canonical_path(root_canonical, root)

            # 10. Probe candidate path on remote target
            candidate_full_path = os.path.join(root_canonical, norm_rel_path)
            probe = self.transport.probe_remote_path(target_cfg, candidate_full_path)

            # Deny symlink target
            if probe.get("is_symlink"):
                raise PolicyError(f"Target path is a symlink: {relative_path}", code="SYMLINK_WRITE_DENIED")

            # Deny symlink parent
            if probe.get("parent_is_symlink"):
                raise PolicyError(f"Parent directory of '{relative_path}' is a symlink", code="SYMLINK_WRITE_DENIED")

            # Validate parent directory existence and containment within root
            if not probe.get("parent_exists"):
                raise PolicyError(f"Parent directory does not exist for path: {relative_path}", code="NOT_FOUND")

            parent_canon = probe.get("parent_canonical_path", "")
            validate_canonical_path(parent_canon, root_canonical)

            # Preconditions for create vs overwrite
            if create:
                if probe.get("exists"):
                    raise PolicyError(f"File already exists: {relative_path}", code="FILE_ALREADY_EXISTS")
            else:
                if not probe.get("exists"):
                    raise PolicyError(f"File not found: {relative_path}", code="NOT_FOUND")
                if probe.get("is_dir"):
                    raise PolicyError(f"Target path is a directory: {relative_path}", code="INVALID_PATH")

                dest_canon = probe.get("canonical_path", "")
                validate_canonical_path(dest_canon, root_canonical)

                if not expected_sha256:
                    raise PolicyError(
                        "expected_sha256 is required when overwriting an existing file",
                        code="WRITE_CONFLICT"
                    )

                current_sha = probe.get("sha256", "")
                if current_sha.lower() != expected_sha256.lower():
                    raise PolicyError(
                        f"Hash mismatch: expected {expected_sha256}, found {current_sha}",
                        code="WRITE_CONFLICT"
                    )

            proposed_sha256 = hashlib.sha256(content_bytes).hexdigest()

            # 11. Dry Run Mode
            if dry_run:
                if probe.get("exists"):
                    current_content = probe.get("content", "")
                    current_sha256 = probe.get("sha256", "")
                    size_before = probe.get("size", 0)
                else:
                    current_content = ""
                    current_sha256 = None
                    size_before = 0

                diff_lines = list(difflib.unified_diff(
                    current_content.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"a/{relative_path}",
                    tofile=f"b/{relative_path}",
                ))
                diff_text = "".join(diff_lines)
                max_diff_bytes = int(self._get_setting("max_diff_bytes", 65536))
                diff_bytes = diff_text.encode("utf-8")
                if len(diff_bytes) > max_diff_bytes:
                    diff_text = diff_bytes[:max_diff_bytes].decode("utf-8", errors="replace")
                    diff_truncated = True
                else:
                    diff_truncated = False

                dry_res = {
                    "path": relative_path,
                    "current_sha256": current_sha256,
                    "proposed_sha256": proposed_sha256,
                    "size_before": size_before,
                    "size_after": len(content_bytes),
                    "unified_diff": diff_text,
                    "diff": diff_text,
                    "diff_truncated": diff_truncated,
                    "dry_run": True,
                }
                self._record_audit(
                    action="DRY_RUN", target_id=target, project_id=project,
                    start_time=start_time, success=1, bytes_transferred=len(content_bytes),
                    detail={"path": relative_path, "dry_run": True}
                )
                return self._success_response("write_file", dry_res, target, project, start_time)

            # 12. Create backup on Gateway (retained up to 5 versions)
            backup_path = None
            if not create and probe.get("exists"):
                try:
                    backup_dir = os.path.expanduser(f"~/.local/share/mcp-gateway/backups/{target}/{project}/{norm_rel_path}")
                    os.makedirs(backup_dir, exist_ok=True)
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    old_sha = probe.get("sha256", "unknown")
                    backup_path = os.path.join(backup_dir, f"{ts}_{old_sha[:12]}.bak")
                    with open(backup_path, "wb") as bf:
                        bf.write(probe.get("content", "").encode("utf-8"))
                    b_files = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith(".bak")])
                    if len(b_files) > 5:
                        for old_b in b_files[:-5]:
                            try:
                                os.unlink(old_b)
                            except OSError:
                                pass
                except Exception:
                    pass

            # 13. Real Atomic Write on Target
            write_res = self.transport.write_remote_file_atomic(
                target=target_cfg,
                dest_path=candidate_full_path,
                content_bytes=content_bytes,
                create=create,
                expected_sha256=expected_sha256,
                max_write_bytes=max_write_bytes,
            )

            result = {
                "path": relative_path,
                "created": write_res.get("created", create),
                "old_sha256": write_res.get("old_sha256"),
                "new_sha256": write_res.get("new_sha256", proposed_sha256),
                "sha256": write_res.get("new_sha256", proposed_sha256),
                "bytes_written": write_res.get("bytes_written", len(content_bytes)),
                "backup_path": backup_path,
                "atomic": write_res.get("atomic", True),
            }

            self._record_audit(
                action="WRITE", target_id=target, project_id=project,
                start_time=start_time, success=1, bytes_transferred=len(content_bytes),
                detail=result
            )
            return self._success_response("write_file", result, target, project, start_time)

        except (ConfigError, PolicyError) as e:
            self._record_audit(
                action="DENY", target_id=target, project_id=project,
                start_time=start_time, success=0, error_code=e.code,
                detail={"path": relative_path, "tool": "write_file"}
            )
            return self._error_response("write_file", e.code, str(e), target, project, start_time)
        except SSHError as e:
            self._record_audit(
                action="DENY", target_id=target, project_id=project,
                start_time=start_time, success=0, error_code=e.code,
                detail={"path": relative_path, "tool": "write_file"}
            )
            return self._error_response("write_file", e.code, str(e), target, project, start_time)
        except Exception as e:
            self._record_audit(
                action="DENY", target_id=target, project_id=project,
                start_time=start_time, success=0, error_code="INTERNAL_ERROR",
                detail={"path": relative_path, "tool": "write_file"}
            )
            return self._error_response("write_file", "INTERNAL_ERROR", str(e), target, project, start_time)

    def gateway_status(self) -> Dict[str, Any]:
        """Return system metrics (RAM, zram, CPU, storage, temp), service status, and registry info."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("gateway_status", start_time=start_time)
        if gw_check:
            return gw_check
        try:
            uptime_sec = 0
            if os.path.isfile("/proc/uptime"):
                try:
                    with open("/proc/uptime", "r") as f:
                        uptime_sec = int(float(f.read().split()[0]))
                except Exception:
                    pass

            load_1, load_5, load_15 = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)

            mem = {"total_mb": 0, "available_mb": 0, "used_mb": 0}
            if os.path.isfile("/proc/meminfo"):
                try:
                    meminfo = {}
                    with open("/proc/meminfo", "r") as f:
                        for line in f:
                            parts = line.split(":")
                            if len(parts) == 2:
                                key = parts[0].strip()
                                val = parts[1].strip().split()[0]
                                if val.isdigit():
                                    meminfo[key] = int(val)
                    total_kb = meminfo.get("MemTotal", 0)
                    avail_kb = meminfo.get("MemAvailable", 0)
                    mem["total_mb"] = total_kb // 1024
                    mem["available_mb"] = avail_kb // 1024
                    mem["used_mb"] = (total_kb - avail_kb) // 1024
                except Exception:
                    pass

            zram_used_mb = 0
            if os.path.isfile("/sys/block/zram0/mem_used_total"):
                try:
                    with open("/sys/block/zram0/mem_used_total", "r") as f:
                        zram_used_mb = int(f.read().strip()) // (1024 * 1024)
                except Exception:
                    pass

            disk = shutil.disk_usage("/")
            disk_info = {
                "root_total_gb": round(disk.total / (1024**3), 2),
                "root_used_gb": round(disk.used / (1024**3), 2),
                "root_free_gb": round(disk.free / (1024**3), 2),
                "root_used_pct": round((disk.used / disk.total) * 100, 1),
            }

            temp_c = None
            if os.path.isfile("/sys/class/thermal/thermal_zone0/temp"):
                try:
                    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                        temp_c = round(int(f.read().strip()) / 1000.0, 1)
                except Exception:
                    pass

            throttled = "unknown"
            if shutil.which("vcgencmd"):
                try:
                    cp = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=3)
                    if cp.returncode == 0 and "=" in cp.stdout:
                        throttled = cp.stdout.strip().split("=")[1]
                except Exception:
                    pass

            services = {}
            if shutil.which("systemctl"):
                for svc in ("mcp-gateway-admin", "mcp-gateway-mcp"):
                    try:
                        cp = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=3)
                        services[svc] = cp.stdout.strip()
                    except Exception:
                        services[svc] = "unknown"

            db_path = getattr(self.config, "db_path", None)
            if not db_path:
                from .lifecycle import get_paths
                db_path = get_paths()["db"]
            db_size = os.path.getsize(db_path) if os.path.isfile(db_path) else 0

            res = {
                "gateway_status": "ok" if self._is_gateway_enabled() else "disabled",
                "gateway_version": __version__,
                "architecture": platform.machine(),
                "python_version": platform.python_version(),
                "uptime_seconds": uptime_sec,
                "cpu_load": {"1m": round(load_1, 2), "5m": round(load_5, 2), "15m": round(load_15, 2)},
                "memory": mem,
                "zram_used_mb": zram_used_mb,
                "storage": disk_info,
                "temperature_c": temp_c,
                "throttled": throttled,
                "services": services,
                "database": {
                    "path": db_path,
                    "size_bytes": db_size,
                    "writes_enabled": self._is_writes_enabled(),
                    "targets_count": self.config.target_count if hasattr(self.config, "target_count") else 0,
                },
            }
            self._record_audit("STATUS_CHECK", detail={"tool": "gateway_status"})
            return self._success_response("gateway_status", res, start_time=start_time)
        except Exception as e:
            return self._error_response("gateway_status", "INTERNAL_ERROR", str(e), start_time=start_time)

    def gateway_doctor(self) -> Dict[str, Any]:
        """Execute unified system health and integrity check."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("gateway_doctor", start_time=start_time)
        if gw_check:
            return gw_check
        try:
            from .doctor import run_doctor
            status, check_objs = run_doctor(verbose=False)
            checks_data = []
            passed_cnt = 0
            failed_cnt = 0
            warn_cnt = 0
            for c in check_objs:
                checks_data.append({
                    "name": c.name,
                    "passed": c.passed,
                    "message": c.message,
                    "severity": c.severity,
                })
                if c.passed:
                    passed_cnt += 1
                elif c.severity == "warning":
                    warn_cnt += 1
                else:
                    failed_cnt += 1

            res = {
                "status": status,
                "checks_count": len(check_objs),
                "passed": passed_cnt,
                "failed": failed_cnt,
                "warnings": warn_cnt,
                "checks": checks_data,
            }
            self._record_audit("DOCTOR_CHECK", detail={"status": status, "passed": passed_cnt, "failed": failed_cnt})
            return self._success_response("gateway_doctor", res, start_time=start_time)
        except Exception as e:
            return self._error_response("gateway_doctor", "INTERNAL_ERROR", str(e), start_time=start_time)

    def gateway_backup(self) -> Dict[str, Any]:
        """Generate safe online SQLite backup of gateway registry database."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("gateway_backup", start_time=start_time)
        if gw_check:
            return gw_check
        try:
            from .lifecycle import backup_database
            bak_path = backup_database()
            h = hashlib.sha256()
            with open(bak_path, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            sha256_hex = h.hexdigest()
            size = os.path.getsize(bak_path)

            res = {
                "backup_path": bak_path,
                "sha256": sha256_hex,
                "size_bytes": size,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self._record_audit("REGISTRY_BACKUP", bytes_transferred=size, detail={"backup_path": bak_path, "sha256": sha256_hex})
            return self._success_response("gateway_backup", res, start_time=start_time)
        except Exception as e:
            return self._error_response("gateway_backup", "INTERNAL_ERROR", str(e), start_time=start_time)

    def gateway_maintenance(self) -> Dict[str, Any]:
        """Execute automated safe maintenance (online backup, backup rotation, DB integrity check, Doctor)."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("gateway_maintenance", start_time=start_time)
        if gw_check:
            return gw_check
        try:
            from .lifecycle import backup_database, get_paths
            from .doctor import run_doctor

            bak_path = backup_database()
            b_size = os.path.getsize(bak_path)

            paths = get_paths()
            backups_dir = paths["backups"]
            pruned_count = 0
            if os.path.isdir(backups_dir):
                b_files = sorted(
                    [os.path.join(backups_dir, f) for f in os.listdir(backups_dir) if f.startswith("gateway_backup_") and f.endswith(".db")],
                    key=os.path.getmtime
                )
                if len(b_files) > 5:
                    for old_b in b_files[:-5]:
                        try:
                            os.remove(old_b)
                            pruned_count += 1
                        except OSError:
                            pass

            db_path = paths["db"]
            integrity = "unknown"
            if os.path.isfile(db_path):
                conn = sqlite3.connect(db_path)
                row = conn.execute("PRAGMA integrity_check;").fetchone()
                integrity = row[0] if row else "failed"
                conn.close()

            doc_status, _ = run_doctor(verbose=False)

            disk = shutil.disk_usage("/")
            mem_avail_mb = 0
            if os.path.isfile("/proc/meminfo"):
                try:
                    with open("/proc/meminfo", "r") as f:
                        for line in f:
                            if line.startswith("MemAvailable:"):
                                mem_avail_mb = int(line.split(":")[1].strip().split()[0]) // 1024
                                break
                except Exception:
                    pass

            sec_status = "unattended-upgrades not installed"
            log_path = "/var/log/unattended-upgrades/unattended-upgrades.log"
            conf_path = "/etc/apt/apt.conf.d/50unattended-upgrades"
            if os.path.isfile(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = [l.strip() for l in f if l.strip()]
                        sec_status = lines[-1] if lines else "active (idle)"
                except Exception:
                    sec_status = "active"
            elif os.path.isfile(conf_path):
                sec_status = "configured (security-only, no reboot)"

            res = {
                "message": "Appliance maintenance executed successfully",
                "backup_created": bak_path,
                "backup_size_bytes": b_size,
                "pruned_backups_count": pruned_count,
                "database_integrity": integrity,
                "doctor_status": doc_status,
                "security_updates": sec_status,
                "resources": {
                    "disk_free_gb": round(disk.free / (1024**3), 2),
                    "memory_available_mb": mem_avail_mb,
                },
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self._record_audit("MAINTENANCE_RUN", detail={"doctor_status": doc_status, "pruned": pruned_count})
            return self._success_response("gateway_maintenance", res, start_time=start_time)
        except Exception as e:
            return self._error_response("gateway_maintenance", "INTERNAL_ERROR", str(e), start_time=start_time)

    def gateway_reboot(self, confirm: bool = False) -> Dict[str, Any]:
        """Request controlled reboot of the MCP-Pi appliance."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("gateway_reboot", start_time=start_time)
        if gw_check:
            return gw_check

        if confirm is not True:
            return self._error_response(
                "gateway_reboot",
                "INVALID_ARGUMENTS",
                "Appliance reboot requires explicit confirmation parameter 'confirm=True'",
                start_time=start_time,
            )

        try:
            self._record_audit("REBOOT_REQUESTED", detail={"actor": self.client_id, "tool": "gateway_reboot"})

            helper_path = "/usr/local/bin/mcp-gateway-reboot"
            if os.path.isfile(helper_path) and platform.system() == "Linux":
                subprocess.Popen(
                    ["sh", "-c", "sleep 2 && sudo /usr/local/bin/mcp-gateway-reboot"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                reboot_scheduled = True
                msg = "Controlled appliance reboot scheduled in 2 seconds"
            elif platform.system() == "Windows":
                reboot_scheduled = False
                msg = "Reboot requested (simulated on Windows development platform)"
            else:
                reboot_scheduled = False
                msg = f"Reboot helper {helper_path} not found"

            res = {
                "reboot_scheduled": reboot_scheduled,
                "message": msg,
                "requested_by": self.client_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            return self._success_response("gateway_reboot", res, start_time=start_time)
        except Exception as e:
            return self._error_response("gateway_reboot", "INTERNAL_ERROR", str(e), start_time=start_time)

    def run_command(
        self,
        target: str,
        project: Optional[str],
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        stdin: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a shell command in the target worker environment."""
        start_time = time.monotonic()
        if not project:
            try:
                t_cfg = self.config.get_target(target)
                projs = t_cfg.get("projects", {})
                if len(projs) == 1:
                    project = list(projs.keys())[0]
                elif "MCP_Local" in projs:
                    project = "MCP_Local"
                elif projs:
                    project = list(projs.keys())[0]
            except Exception:
                pass

        gw_check = self._check_gateway_enabled("run_command", target=target, project=project, start_time=start_time)
        if gw_check:
            return gw_check

        if not command or not isinstance(command, str) or not command.strip():
            return self._error_response("run_command", "INVALID_ARGUMENTS", "Command must be a non-empty string", target, project, start_time)

        try:
            target_cfg = self.config.get_target(target)
            project_cfg = self.config.get_project(target, project)
            root = project_cfg["root"]
            root_canonical = self.transport.resolve_canonical_path(target_cfg, root)
            validate_canonical_path(root_canonical, root)

            # Resolve effective_cwd
            if not cwd or str(cwd).strip() in (".", ""):
                effective_cwd = root_canonical
            elif os.path.isabs(cwd):
                norm_cwd = os.path.normpath(cwd)
                validate_canonical_path(norm_cwd, root_canonical)
                effective_cwd = norm_cwd
            else:
                norm_rel = validate_relative_path(cwd)
                cand_cwd = os.path.normpath(os.path.join(root_canonical, norm_rel))
                validate_canonical_path(cand_cwd, root_canonical)
                effective_cwd = cand_cwd

            # Scope principle: block obvious attempts to tamper with other private project directories outside MCP_Local
            import re
            m = re.search(r'(?:~/|/data/data/com\.termux/files/home/)[Pp]rojects/([^/\s\'";]+)', command)
            if m:
                proj_name = m.group(1)
                expected_proj = os.path.basename(root.rstrip("/"))
                if proj_name != expected_proj:
                    raise PolicyError(f"Access to unauthorized project '{proj_name}' is blocked", code="PATH_OUTSIDE_ALLOWED_ROOT")

            input_bytes = stdin.encode("utf-8") if stdin else None
            effective_timeout = int(timeout) if timeout else None

            res = self.transport.run_command(
                target=target_cfg,
                remote_cmd=command,
                timeout=effective_timeout,
                cwd=effective_cwd,
                env=env if isinstance(env, dict) else None,
                input_data=input_bytes,
                request_id=self.request_id,
            )

            duration_sec = round(res.duration_ms / 1000.0, 3)
            result_data = {
                "stdout": res.stdout,
                "stderr": res.stderr,
                "exit_code": res.exit_code,
                "timed_out": getattr(res, "timed_out", False),
                "duration": duration_sec,
                "effective_cwd": effective_cwd,
            }

            self._record_audit(
                "RUN_COMMAND",
                target_id=target,
                project_id=project,
                start_time=start_time,
                success=1 if res.exit_code == 0 else 0,
                detail={"command": command[:100], "exit_code": res.exit_code, "cwd": effective_cwd},
            )

            return self._success_response("run_command", result_data, target, project, start_time)

        except PolicyError as e:
            self._record_audit(
                "DENY",
                target_id=target,
                project_id=project,
                start_time=start_time,
                success=0,
                error_code=e.code,
                detail={"error": str(e), "command": command[:100]},
            )
            return self._error_response("run_command", e.code, str(e), target, project, start_time)
        except SSHError as e:
            if e.code == "SSH_TIMEOUT":
                duration_sec = round((time.monotonic() - start_time), 3)
                result_data = {
                    "stdout": "",
                    "stderr": str(e),
                    "exit_code": 124,
                    "timed_out": True,
                    "duration": duration_sec,
                    "effective_cwd": effective_cwd if 'effective_cwd' in locals() else root,
                }
                return self._success_response("run_command", result_data, target, project, start_time)
            self._record_audit(
                "ERROR",
                target_id=target,
                project_id=project,
                start_time=start_time,
                success=0,
                error_code=e.code,
                detail={"error": str(e)},
            )
            return self._error_response("run_command", e.code, str(e), target, project, start_time)
        except Exception as e:
            return self._error_response("run_command", "INTERNAL_ERROR", str(e), target, project, start_time)

    def append_file(self, target: str, project: str, path: str, content: str) -> Dict[str, Any]:
        """Append UTF-8 content to an existing file in the project."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("append_file", target=target, project=project, start_time=start_time)
        if gw_check:
            return gw_check

        writes_enabled = str(self._get_setting("writes_enabled", "true")).lower() == "true"
        if not writes_enabled:
            return self._error_response("append_file", "WRITES_DISABLED", "Controlled writes are disabled", target, project, start_time)

        try:
            target_cfg = self.config.get_target(target)
            project_cfg = self.config.get_project(target, project)
            check_capability(project_cfg, "write")

            content_bytes = validate_content_utf8(content)
            max_write_bytes = int(self._get_setting("max_write_bytes", 262144))
            validate_write_size(content_bytes, max_write_bytes)

            norm_rel_path = validate_write_relative_path(path)
            root = project_cfg["root"]
            root_canonical = self.transport.resolve_canonical_path(target_cfg, root)
            validate_canonical_path(root_canonical, root)

            candidate_full_path = os.path.join(root_canonical, norm_rel_path)
            probe = self.transport.probe_remote_path(target_cfg, candidate_full_path)
            if not probe.get("exists"):
                raise PolicyError(f"File not found: {path}", code="NOT_FOUND")
            if probe.get("is_dir") or probe.get("is_symlink"):
                raise PolicyError(f"Cannot append to directory or symlink: {path}", code="INVALID_PATH")

            dest_canon = probe.get("canonical_path", candidate_full_path)
            validate_canonical_path(dest_canon, root_canonical)

            append_script = (
                f"import sys, hashlib; p = {json.dumps(dest_canon)}; "
                f"data = sys.stdin.buffer.read(); "
                f"open(p, 'ab').write(data); "
                f"print(hashlib.sha256(open(p, 'rb').read()).hexdigest())"
            )
            res = self.transport.run_command(
                target=target_cfg,
                remote_cmd=f"python3 -c {shlex.quote(append_script)}",
                input_data=content_bytes,
                timeout=15,
            )
            if res.exit_code != 0:
                raise PolicyError(f"Append failed: {res.stderr}", code="WRITE_FAILED")

            new_sha256 = res.stdout.strip()
            result_data = {
                "path": norm_rel_path,
                "bytes_appended": len(content_bytes),
                "new_sha256": new_sha256,
            }
            self._record_audit(
                "APPEND_FILE",
                target_id=target,
                project_id=project,
                start_time=start_time,
                success=1,
                detail={"path": norm_rel_path, "bytes": len(content_bytes)},
            )
            return self._success_response("append_file", result_data, target, project, start_time)
        except PolicyError as e:
            return self._error_response("append_file", e.code, str(e), target, project, start_time)
        except Exception as e:
            return self._error_response("append_file", "INTERNAL_ERROR", str(e), target, project, start_time)

    def delete_file(self, target: str, project: str, path: str) -> Dict[str, Any]:
        """Delete a file or empty directory within the project."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("delete_file", target=target, project=project, start_time=start_time)
        if gw_check:
            return gw_check

        writes_enabled = str(self._get_setting("writes_enabled", "true")).lower() == "true"
        if not writes_enabled:
            return self._error_response("delete_file", "WRITES_DISABLED", "Controlled writes are disabled", target, project, start_time)

        try:
            target_cfg = self.config.get_target(target)
            project_cfg = self.config.get_project(target, project)
            check_capability(project_cfg, "write")

            norm_rel_path = validate_write_relative_path(path)
            root = project_cfg["root"]
            root_canonical = self.transport.resolve_canonical_path(target_cfg, root)
            validate_canonical_path(root_canonical, root)

            candidate_full_path = os.path.join(root_canonical, norm_rel_path)
            if candidate_full_path == root_canonical:
                raise PolicyError("Deleting project root is forbidden", code="INVALID_PATH")

            probe = self.transport.probe_remote_path(target_cfg, candidate_full_path)
            if not probe.get("exists"):
                raise PolicyError(f"File not found: {path}", code="NOT_FOUND")

            dest_canon = probe.get("canonical_path", candidate_full_path)
            validate_canonical_path(dest_canon, root_canonical)

            del_script = (
                f"import os; p = {json.dumps(dest_canon)}; "
                f"os.remove(p) if os.path.isfile(p) or os.path.islink(p) else os.rmdir(p)"
            )
            res = self.transport.run_command(
                target=target_cfg,
                remote_cmd=f"python3 -c {shlex.quote(del_script)}",
                timeout=15,
            )
            if res.exit_code != 0:
                raise PolicyError(f"Delete failed: {res.stderr}", code="DELETE_FAILED")

            result_data = {"path": norm_rel_path, "deleted": True}
            self._record_audit(
                "DELETE_FILE",
                target_id=target,
                project_id=project,
                start_time=start_time,
                success=1,
                detail={"path": norm_rel_path},
            )
            return self._success_response("delete_file", result_data, target, project, start_time)
        except PolicyError as e:
            return self._error_response("delete_file", e.code, str(e), target, project, start_time)
        except Exception as e:
            return self._error_response("delete_file", "INTERNAL_ERROR", str(e), target, project, start_time)

    def copy_file(self, target: str, project: str, source_path: str, dest_path: str) -> Dict[str, Any]:
        """Copy a file within the project."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("copy_file", target=target, project=project, start_time=start_time)
        if gw_check:
            return gw_check

        writes_enabled = str(self._get_setting("writes_enabled", "true")).lower() == "true"
        if not writes_enabled:
            return self._error_response("copy_file", "WRITES_DISABLED", "Controlled writes are disabled", target, project, start_time)

        try:
            target_cfg = self.config.get_target(target)
            project_cfg = self.config.get_project(target, project)
            check_capability(project_cfg, "write")

            norm_src = validate_write_relative_path(source_path)
            norm_dst = validate_write_relative_path(dest_path)
            root = project_cfg["root"]
            root_canonical = self.transport.resolve_canonical_path(target_cfg, root)
            validate_canonical_path(root_canonical, root)

            src_full = os.path.join(root_canonical, norm_src)
            dst_full = os.path.join(root_canonical, norm_dst)

            probe_src = self.transport.probe_remote_path(target_cfg, src_full)
            if not probe_src.get("exists"):
                raise PolicyError(f"Source file not found: {source_path}", code="NOT_FOUND")

            src_canon = probe_src.get("canonical_path", src_full)
            validate_canonical_path(src_canon, root_canonical)

            dst_parent = os.path.dirname(dst_full)
            validate_canonical_path(dst_parent, root_canonical)

            cp_script = f"import shutil; shutil.copy2({json.dumps(src_canon)}, {json.dumps(dst_full)})"
            res = self.transport.run_command(target=target_cfg, remote_cmd=f"python3 -c {shlex.quote(cp_script)}", timeout=15)
            if res.exit_code != 0:
                raise PolicyError(f"Copy failed: {res.stderr}", code="WRITE_FAILED")

            result_data = {"source": norm_src, "dest": norm_dst, "copied": True}
            self._record_audit(
                "COPY_FILE",
                target_id=target,
                project_id=project,
                start_time=start_time,
                success=1,
                detail={"source": norm_src, "dest": norm_dst},
            )
            return self._success_response("copy_file", result_data, target, project, start_time)
        except PolicyError as e:
            return self._error_response("copy_file", e.code, str(e), target, project, start_time)
        except Exception as e:
            return self._error_response("copy_file", "INTERNAL_ERROR", str(e), target, project, start_time)

    def move_file(self, target: str, project: str, source_path: str, dest_path: str) -> Dict[str, Any]:
        """Move or rename a file within the project."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("move_file", target=target, project=project, start_time=start_time)
        if gw_check:
            return gw_check

        writes_enabled = str(self._get_setting("writes_enabled", "true")).lower() == "true"
        if not writes_enabled:
            return self._error_response("move_file", "WRITES_DISABLED", "Controlled writes are disabled", target, project, start_time)

        try:
            target_cfg = self.config.get_target(target)
            project_cfg = self.config.get_project(target, project)
            check_capability(project_cfg, "write")

            norm_src = validate_write_relative_path(source_path)
            norm_dst = validate_write_relative_path(dest_path)
            root = project_cfg["root"]
            root_canonical = self.transport.resolve_canonical_path(target_cfg, root)
            validate_canonical_path(root_canonical, root)

            src_full = os.path.join(root_canonical, norm_src)
            dst_full = os.path.join(root_canonical, norm_dst)

            probe_src = self.transport.probe_remote_path(target_cfg, src_full)
            if not probe_src.get("exists"):
                raise PolicyError(f"Source file not found: {source_path}", code="NOT_FOUND")

            src_canon = probe_src.get("canonical_path", src_full)
            validate_canonical_path(src_canon, root_canonical)

            dst_parent = os.path.dirname(dst_full)
            validate_canonical_path(dst_parent, root_canonical)

            mv_script = f"import shutil; shutil.move({json.dumps(src_canon)}, {json.dumps(dst_full)})"
            res = self.transport.run_command(target=target_cfg, remote_cmd=f"python3 -c {shlex.quote(mv_script)}", timeout=15)
            if res.exit_code != 0:
                raise PolicyError(f"Move failed: {res.stderr}", code="WRITE_FAILED")

            result_data = {"source": norm_src, "dest": norm_dst, "moved": True}
            self._record_audit(
                "MOVE_FILE",
                target_id=target,
                project_id=project,
                start_time=start_time,
                success=1,
                detail={"source": norm_src, "dest": norm_dst},
            )
            return self._success_response("move_file", result_data, target, project, start_time)
        except PolicyError as e:
            return self._error_response("move_file", e.code, str(e), target, project, start_time)
        except Exception as e:
            return self._error_response("move_file", "INTERNAL_ERROR", str(e), target, project, start_time)

    def mkdir(self, target: str, project: str, path: str, parents: bool = True) -> Dict[str, Any]:
        """Create a directory within the project."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("mkdir", target=target, project=project, start_time=start_time)
        if gw_check:
            return gw_check

        writes_enabled = str(self._get_setting("writes_enabled", "true")).lower() == "true"
        if not writes_enabled:
            return self._error_response("mkdir", "WRITES_DISABLED", "Controlled writes are disabled", target, project, start_time)

        try:
            target_cfg = self.config.get_target(target)
            project_cfg = self.config.get_project(target, project)
            check_capability(project_cfg, "write")

            norm_rel_path = validate_write_relative_path(path)
            root = project_cfg["root"]
            root_canonical = self.transport.resolve_canonical_path(target_cfg, root)
            validate_canonical_path(root_canonical, root)

            candidate_full_path = os.path.join(root_canonical, norm_rel_path)
            validate_canonical_path(candidate_full_path, root_canonical)

            mkdir_script = f"import os; os.makedirs({json.dumps(candidate_full_path)}, exist_ok={bool(parents)})"
            res = self.transport.run_command(target=target_cfg, remote_cmd=f"python3 -c {shlex.quote(mkdir_script)}", timeout=15)
            if res.exit_code != 0:
                raise PolicyError(f"mkdir failed: {res.stderr}", code="WRITE_FAILED")

            result_data = {"path": norm_rel_path, "created": True}
            self._record_audit(
                "MKDIR",
                target_id=target,
                project_id=project,
                start_time=start_time,
                success=1,
                detail={"path": norm_rel_path},
            )
            return self._success_response("mkdir", result_data, target, project, start_time)
        except PolicyError as e:
            return self._error_response("mkdir", e.code, str(e), target, project, start_time)
        except Exception as e:
            return self._error_response("mkdir", "INTERNAL_ERROR", str(e), target, project, start_time)

    def search(self, target: str, project: str, pattern: str, path: Optional[str] = ".", is_regex: bool = False) -> Dict[str, Any]:
        """Search text/patterns within files in the project."""
        start_time = time.monotonic()
        gw_check = self._check_gateway_enabled("search", target=target, project=project, start_time=start_time)
        if gw_check:
            return gw_check

        if not pattern:
            return self._error_response("search", "INVALID_ARGUMENTS", "Pattern must not be empty", target, project, start_time)

        try:
            target_cfg = self.config.get_target(target)
            project_cfg = self.config.get_project(target, project)
            check_capability(project_cfg, "read")

            rel_dir = validate_relative_path(path or ".")
            root = project_cfg["root"]
            root_canonical = self.transport.resolve_canonical_path(target_cfg, root)
            validate_canonical_path(root_canonical, root)

            search_dir = os.path.normpath(os.path.join(root_canonical, rel_dir))
            validate_canonical_path(search_dir, root_canonical)

            search_script = (
                f"import os, re, json; "
                f"pat = {json.dumps(pattern)}; is_re = {json.dumps(bool(is_regex))}; "
                f"regex = re.compile(pat) if is_re else None; "
                f"matches = []; base = {json.dumps(search_dir)}; "
                f"for r, dirs, files in os.walk(base): "
                f"    dirs[:] = [d for d in dirs if not d.startswith('.git') and not d.startswith('__pycache__')]; "
                f"    for f in files: "
                f"        fp = os.path.join(r, f); "
                f"        try: "
                f"            with open(fp, 'r', encoding='utf-8', errors='ignore') as fh: "
                f"                for idx, line in enumerate(fh, 1): "
                f"                    hit = (regex.search(line) if is_re else (pat in line)); "
                f"                    if hit: "
                f"                        rel_f = os.path.relpath(fp, {json.dumps(root_canonical)}); "
                f"                        matches.append({{'file': rel_f, 'line': idx, 'text': line.strip()[:200]}}); "
                f"                        if len(matches) >= 100: break "
                f"        except Exception: pass\n"
                f"        if len(matches) >= 100: break\n"
                f"    if len(matches) >= 100: break\n"
                f"print(json.dumps(matches))"
            )
            res = self.transport.run_command(target=target_cfg, remote_cmd=f"python3 -c {shlex.quote(search_script)}", timeout=20)
            matches = []
            if res.exit_code == 0 and res.stdout.strip():
                try:
                    matches = json.loads(res.stdout)
                except Exception:
                    pass

            result_data = {"pattern": pattern, "path": rel_dir, "matches": matches, "count": len(matches)}
            self._record_audit(
                "SEARCH",
                target_id=target,
                project_id=project,
                start_time=start_time,
                success=1,
                detail={"pattern": pattern, "count": len(matches)},
            )
            return self._success_response("search", result_data, target, project, start_time)
        except PolicyError as e:
            return self._error_response("search", e.code, str(e), target, project, start_time)
        except Exception as e:
            return self._error_response("search", "INTERNAL_ERROR", str(e), target, project, start_time)



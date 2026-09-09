"""Standard tools implementation for MCP Gateway."""

import difflib
import hashlib
import json
import os
import platform
import shlex
import socket
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
        self.transport = transport or SSHTransport()
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


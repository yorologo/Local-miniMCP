"""Standard tools implementation for MCP Gateway."""

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
    check_capability,
    validate_canonical_path,
    validate_relative_path,
    validate_task,
)
from .ssh_transport import SSHError, SSHTransport


class GatewayTools:
    """Provides high-level, audited operations on configured targets."""

    def __init__(
        self,
        config: Optional[GatewayConfig] = None,
        transport: Optional[SSHTransport] = None,
        registry: Optional[Any] = None,
    ):
        self.config = registry or config or GatewayConfig.load()
        self.transport = transport or SSHTransport()

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
        return None

    def health(self) -> Dict[str, Any]:
        """Return gateway status and system metadata."""
        start_time = time.monotonic()
        try:
            is_enabled = self._is_gateway_enabled()
            res = {
                "gateway_status": "ok" if is_enabled else "disabled",
                "gateway_enabled": is_enabled,
                "hostname": socket.gethostname(),
                "gateway_version": __version__,
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
            res = self.transport.run_command(target_cfg, "hostname", timeout=10)
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
            res = self.transport.run_command(target_cfg, cmd, timeout=15)

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
            res = self.transport.run_command(target_cfg, cmd, timeout=10)

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

            result = {
                "relative_path": relative_path,
                "canonical_path": canonical,
                "size_bytes": len(content.encode("utf-8")),
                "content": content,
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

            res = self.transport.run_command(target_cfg, "git status --short", cwd=canonical, timeout=20)
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
                target_cfg, quoted_cmd, cwd=canonical, timeout=task_def["timeout"]
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

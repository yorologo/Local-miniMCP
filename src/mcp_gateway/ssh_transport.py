"""SSH transport wrapper for remote execution across configured targets."""

import os
import shlex
import subprocess
import time
from typing import Any, Dict, List, Optional


class SSHError(Exception):
    """Raised when an SSH transport execution fails or times out."""

    def __init__(self, message: str, code: str = "SSH_FAILED", exit_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


class SSHTransportResult:
    """Result of an SSH remote command execution."""

    def __init__(self, exit_code: int, stdout: str, stderr: str, duration_ms: int):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration_ms = duration_ms

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class SSHTransport:
    """Invokes system OpenSSH via subprocess for target operations."""

    DEFAULT_TIMEOUT = 30
    MAX_OUTPUT_BYTES = 262144     # 256 KiB
    MAX_FILE_READ_BYTES = 1048576  # 1 MiB

    def __init__(
        self,
        default_timeout: int = DEFAULT_TIMEOUT,
        max_output_bytes: int = MAX_OUTPUT_BYTES,
        max_file_read_bytes: int = MAX_FILE_READ_BYTES,
        ssh_binary: str = "ssh",
    ):
        self.default_timeout = default_timeout
        self.max_output_bytes = max_output_bytes
        self.max_file_read_bytes = max_file_read_bytes
        self.ssh_binary = ssh_binary

    def _build_ssh_args(self, target: Dict[str, Any], timeout: int) -> List[str]:
        """Construct SSH argument list using alias or host parameters."""
        alias = target.get("ssh_alias")
        base_cmd = [
            self.ssh_binary,
            "-o", "BatchMode=yes",
            "-o", f"ConnectTimeout={min(timeout, 10)}",
        ]

        if alias:
            base_cmd.append(alias)
        else:
            host = target["host"]
            port = str(target.get("port", 22))
            user = target["user"]
            base_cmd.extend(["-p", port, f"{user}@{host}"])

        return base_cmd

    def run_command(
        self,
        target: Dict[str, Any],
        remote_cmd: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
    ) -> SSHTransportResult:
        """Execute a remote shell command string safely constructed by the gateway."""
        effective_timeout = timeout or self.default_timeout

        if cwd:
            full_remote_cmd = f"cd {shlex.quote(cwd)} && {remote_cmd}"
        else:
            full_remote_cmd = remote_cmd

        ssh_args = self._build_ssh_args(target, effective_timeout)
        ssh_args.append(full_remote_cmd)

        start_time = time.monotonic()
        try:
            proc = subprocess.run(
                ssh_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=effective_timeout,
                check=False,
            )
            duration_ms = int((time.monotonic() - start_time) * 1000)
        except subprocess.TimeoutExpired as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            raise SSHError(
                f"SSH command timed out after {effective_timeout}s",
                code="SSH_TIMEOUT",
            )
        except OSError as e:
            raise SSHError(f"Failed to invoke ssh binary '{self.ssh_binary}': {e}", code="SSH_FAILED")

        # Truncate output if it exceeds max_output_bytes
        stdout_raw = proc.stdout
        stderr_raw = proc.stderr

        stdout_str = stdout_raw[:self.max_output_bytes].decode("utf-8", errors="replace")
        stderr_str = stderr_raw[:self.max_output_bytes].decode("utf-8", errors="replace")

        return SSHTransportResult(
            exit_code=proc.returncode,
            stdout=stdout_str,
            stderr=stderr_str,
            duration_ms=duration_ms,
        )

    def resolve_canonical_path(
        self, target: Dict[str, Any], candidate_path: str, timeout: int = 10
    ) -> str:
        """Resolve the remote canonical realpath of a candidate path."""
        # Use python on the remote system to resolve realpath reliably across POSIX/Windows/Android
        py_code = "import os, sys; print(os.path.realpath(sys.argv[1]))"
        remote_cmd = f"python3 -c {shlex.quote(py_code)} {shlex.quote(candidate_path)} 2>/dev/null || realpath -m {shlex.quote(candidate_path)}"

        res = self.run_command(target, remote_cmd, timeout=timeout)
        if not res.ok or not res.stdout.strip():
            raise SSHError(
                f"Unable to resolve canonical path on target: {res.stderr.strip()}",
                code="SSH_FAILED",
                exit_code=res.exit_code,
            )

        canonical = res.stdout.strip().splitlines()[-1].strip()
        return canonical

    def read_remote_file_content(
        self, target: Dict[str, Any], canonical_path: str, max_bytes: Optional[int] = None
    ) -> str:
        """Read text content of a remote file with size and binary checks."""
        limit = max_bytes or self.max_file_read_bytes
        # Read limit + 1 bytes to detect truncation
        py_code = (
            "import sys, os\n"
            "path = sys.argv[1]\n"
            "limit = int(sys.argv[2])\n"
            "if not os.path.exists(path):\n"
            "    sys.exit(2)\n"
            "if os.path.isdir(path):\n"
            "    sys.exit(3)\n"
            "size = os.path.getsize(path)\n"
            "if size > limit:\n"
            "    sys.exit(4)\n"
            "with open(path, 'rb') as f:\n"
            "    data = f.read(limit + 1)\n"
            "if b'\\x00' in data:\n"
            "    sys.exit(5)\n"
            "sys.stdout.buffer.write(data)\n"
        )

        remote_cmd = f"python3 -c {shlex.quote(py_code)} {shlex.quote(canonical_path)} {limit}"
        res = self.run_command(target, remote_cmd, timeout=15)

        if res.exit_code == 2:
            raise SSHError(f"File not found: {canonical_path}", code="NOT_FOUND")
        if res.exit_code == 3:
            raise SSHError(f"Target path is a directory: {canonical_path}", code="INVALID_PATH")
        if res.exit_code == 4:
            raise SSHError(
                f"File size exceeds allowed limit of {limit} bytes",
                code="FILE_TOO_LARGE",
            )
        if res.exit_code == 5:
            raise SSHError("Binary file not supported", code="BINARY_FILE_NOT_SUPPORTED")
        if not res.ok:
            raise SSHError(
                f"Error reading file '{canonical_path}': {res.stderr.strip()}",
                code="SSH_FAILED",
                exit_code=res.exit_code,
            )

        return res.stdout

"""Policy enforcement and path validation for MCP Gateway."""

import os
import re
from typing import Any, Dict


class PolicyError(Exception):
    """Raised when a policy or security check fails."""

    def __init__(self, message: str, code: str = "POLICY_ERROR"):
        super().__init__(message)
        self.code = code


def validate_relative_path(relative_path: str) -> str:
    r"""Validate that the provided path is strictly relative and safe syntactically.

    Rejects:
    - Empty paths
    - Absolute paths (starting with /, \, ~, or drive letters like C:)
    - NUL characters
    - Traversal components ('..')
    - Suspicious empty segments
    """
    if not isinstance(relative_path, str):
        raise PolicyError("Relative path must be a string", code="INVALID_PATH")

    cleaned = relative_path.strip()
    if not cleaned:
        raise PolicyError("Path cannot be empty", code="INVALID_PATH")

    if "\0" in cleaned:
        raise PolicyError("Path contains NUL byte", code="INVALID_PATH")

    # Reject Windows drive letters (e.g., C:, D:)
    if re.match(r"^[a-zA-Z]:", cleaned):
        raise PolicyError("Absolute drive paths are not allowed", code="INVALID_PATH")

    # Reject root/home prefixes
    if cleaned.startswith(("/", "\\", "~")):
        raise PolicyError("Absolute paths are not allowed", code="INVALID_PATH")

    # Normalize separators
    unified = cleaned.replace("\\", "/")

    # Check for empty path segments (e.g. "a//b")
    parts = unified.split("/")
    for part in parts:
        if part == "..":
            raise PolicyError("Parent directory traversal ('..') is not allowed", code="INVALID_PATH")
        if part == "" and len(parts) > 1 and parts.index(part) != len(parts) - 1:
            # Empty segment in the middle (e.g. foo//bar)
            raise PolicyError("Empty path segment is not allowed", code="INVALID_PATH")

    # Clean redundant dots or slashes
    norm = os.path.normpath(unified)
    if norm == ".." or norm.startswith("../"):
        raise PolicyError("Path attempts to escape workspace", code="INVALID_PATH")

    return norm


def validate_canonical_path(canonical_path: str, allowed_root: str) -> None:
    """Verify that canonicalized remote path strictly resides within allowed_root.

    Protects against:
    - Traversal escapes
    - Symlink escapes
    - Sibling-prefix escapes (e.g., /allowed-root vs /allowed-root-evil)
    """
    norm_root = os.path.normpath(allowed_root).rstrip("/")
    if not norm_root:
        norm_root = "/"

    norm_canon = os.path.normpath(canonical_path).rstrip("/")
    if not norm_canon:
        norm_canon = "/"

    if norm_canon == norm_root:
        return

    expected_prefix = norm_root + "/"
    if not norm_canon.startswith(expected_prefix):
        raise PolicyError(
            f"Path '{canonical_path}' resolves outside allowed root '{allowed_root}'",
            code="PATH_OUTSIDE_ALLOWED_ROOT",
        )


def check_capability(project: Dict[str, Any], capability: str) -> None:
    """Verify project permits specified capability ('read' or 'write')."""
    if capability == "read":
        if not project.get("read", True):
            raise PolicyError("Read capability is disabled for this project", code="TOOL_NOT_ALLOWED")
    elif capability == "write":
        if not project.get("write", False):
            raise PolicyError("Write capability is disabled for this project", code="TOOL_NOT_ALLOWED")
    else:
        raise PolicyError(f"Unknown capability: {capability}", code="TOOL_NOT_ALLOWED")


def validate_task(project: Dict[str, Any], task_name: str) -> Dict[str, Any]:
    """Validate that the requested task is explicitly allowlisted and enabled."""
    tasks = project.get("tasks", {})
    if task_name not in tasks:
        raise PolicyError(
            f"Task '{task_name}' is not allowlisted for this project",
            code="TASK_NOT_ALLOWED",
        )

    task_def = tasks[task_name]
    if not task_def.get("enabled", True):
        raise PolicyError(f"Task '{task_name}' is disabled", code="TASK_NOT_ALLOWED")

    return {
        "argv": list(task_def.get("argv", [])),
        "timeout": int(task_def.get("timeout", 30)),
    }

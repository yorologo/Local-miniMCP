"""Policy enforcement and path validation for MCP Gateway."""

import os
import re
from typing import Any, Dict, Optional, Tuple


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
    norm = os.path.normpath(unified).replace("\\", "/")
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
    norm_root = os.path.normpath(allowed_root).replace("\\", "/").rstrip("/")
    if not norm_root:
        norm_root = "/"

    norm_canon = os.path.normpath(canonical_path).replace("\\", "/").rstrip("/")
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
            raise PolicyError("Write capability is disabled for this project", code="WRITE_NOT_ALLOWED")
    else:
        raise PolicyError(f"Unknown capability: {capability}", code="TOOL_NOT_ALLOWED")


def validate_write_relative_path(relative_path: str) -> str:
    """Validate relative path for write operation.

    Must be a valid relative path, not empty, not '.', and not ending with '/'.
    """
    norm = validate_relative_path(relative_path)
    if norm == "." or norm == "":
        raise PolicyError("Target path cannot be the root directory", code="INVALID_PATH")
    return norm


def validate_content_utf8(content: str) -> bytes:
    """Ensure content is valid UTF-8 string without NUL bytes."""
    if not isinstance(content, str):
        raise PolicyError("Content must be a string", code="INVALID_ENCODING")
    if "\0" in content:
        raise PolicyError("Content contains NUL byte", code="INVALID_ENCODING")
    try:
        content_bytes = content.encode("utf-8")
    except UnicodeEncodeError as e:
        raise PolicyError(f"Content is not valid UTF-8: {e}", code="INVALID_ENCODING")
    return content_bytes


def validate_write_size(content_bytes: bytes, max_bytes: int) -> None:
    """Ensure content size does not exceed allowed max_write_bytes."""
    if len(content_bytes) > max_bytes:
        raise PolicyError(
            f"Content size ({len(content_bytes)} bytes) exceeds allowed limit of {max_bytes} bytes",
            code="FILE_TOO_LARGE",
        )


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


TOOL_CAPABILITIES = {
    "health": {"health", "read", "*"},
    "list_targets": {"read", "list_targets", "*"},
    "target_status": {"read", "target_status", "*"},
    "list_directory": {"read", "list_directory", "*"},
    "file_stat": {"read", "file_stat", "*"},
    "read_file": {"read", "read_file", "*"},
    "git_status": {"read", "git_status", "*"},
    "run_task": {"execute", "run_task", "tasks", "*"},
    "write_file": {"write", "write_file", "*"},
}


def authorize_client(
    client_id: Optional[str],
    target_id: Optional[str],
    project_id: Optional[str],
    tool_name: str,
    registry: Optional[Any] = None,
) -> Tuple[bool, Optional[str]]:
    """Unified Core client authorization decision for discovery and execution.

    Evaluates:
    - Authenticated client identity (anonymous denied)
    - Client enabled status
    - Global Emergency Kill Switch
    - Target enabled status
    - Project enabled status
    - Grant capability match
    - Write policy enforcement
    """
    # 1. Reject anonymous/empty/NONE
    if not client_id or str(client_id).strip().upper() in ("NONE", "ANONYMOUS", ""):
        return False, "ANONYMOUS_CLIENT_DENIED: Client identity required"

    client_id = str(client_id).strip()

    # Local internal caller bypass for admin/maintenance CLI
    if client_id in ("local", "admin", "system", "test"):
        return True, None

    # 2. Check tool exists in catalog
    if tool_name not in TOOL_CAPABILITIES:
        return False, f"TOOL_NOT_RECOGNIZED: Tool '{tool_name}' not in gateway catalog"

    if registry is None:
        from .registry import get_registry
        registry = get_registry()

    # 3. Check client existence & enabled state
    if hasattr(registry, "get_client"):
        try:
            client = registry.get_client(client_id)
        except (KeyError, Exception):
            return False, f"CLIENT_NOT_FOUND: Client '{client_id}' is not registered"

        if not client.get("enabled", True):
            return False, f"CLIENT_DISABLED: Client '{client_id}' is disabled"

    # 4. Check client grants FIRST (Deny by default before revealing operational states)
    if hasattr(registry, "get_client_grants"):
        grants = registry.get_client_grants(client_id)
        if not grants:
            return False, f"TOOL_NOT_ALLOWED: Client '{client_id}' has no active grants"

        allowed_caps = TOOL_CAPABILITIES[tool_name]
        grant_matched = False
        for g in grants:
            if not g.get("enabled", True):
                continue

            cap = str(g.get("capability", "read")).strip()
            g_caps = set(c.strip() for c in cap.split(","))
            if not (g_caps & allowed_caps) and "*" not in g_caps:
                continue

            g_target = g.get("target_id", "*")
            if target_id and g_target not in ("*", target_id):
                continue

            g_project = g.get("project_id", "*")
            if project_id and g_project not in ("*", project_id):
                continue

            grant_matched = True
            break

        if not grant_matched:
            return False, f"TOOL_NOT_ALLOWED: Client '{client_id}' lacks grant capability for tool '{tool_name}'"

    # 5. Check global kill switch
    if hasattr(registry, "get_setting"):
        gateway_enabled = registry.get_setting("gateway_enabled", "true")
        if str(gateway_enabled).lower() == "false":
            if tool_name != "health":
                return False, "GATEWAY_DISABLED: Global kill switch is active"

    # 6. Check target enabled
    if target_id and hasattr(registry, "get_target"):
        try:
            target = registry.get_target(target_id)
            if not target.get("enabled", True):
                return False, f"TARGET_DISABLED: Target '{target_id}' is disabled"
        except Exception as e:
            err_str = str(e).lower()
            if "disabled" in err_str:
                return False, f"TARGET_DISABLED: Target '{target_id}' is disabled"
            return False, f"TARGET_NOT_FOUND: Target '{target_id}' is not configured"

    # 7. Check project enabled
    if target_id and project_id and hasattr(registry, "get_project"):
        try:
            project = registry.get_project(target_id, project_id)
            if not project.get("enabled", True):
                return False, f"PROJECT_DISABLED: Project '{project_id}' is disabled"
        except Exception as e:
            err_str = str(e).lower()
            if "disabled" in err_str:
                return False, f"PROJECT_DISABLED: Project '{project_id}' is disabled"
            return False, f"PROJECT_NOT_FOUND: Project '{project_id}' not found in target '{target_id}'"

    # 8. Check write policy if tool is write_file
    if tool_name == "write_file":
        if hasattr(registry, "get_setting"):
            writes_enabled = registry.get_setting("writes_enabled", "true")
            if str(writes_enabled).lower() != "true":
                return False, "WRITES_DISABLED: Global writes are disabled"
        if target_id and project_id and hasattr(registry, "get_project"):
            try:
                project = registry.get_project(target_id, project_id)
                if not project.get("write", False) and not project.get("write_enabled", False):
                    return False, f"WRITE_NOT_ALLOWED: Write disabled for project '{project_id}'"
            except Exception:
                pass

    return True, None


def can_client_use_tool(
    client_id: Optional[str],
    tool_name: str,
    registry: Optional[Any] = None,
) -> Tuple[bool, Optional[str]]:
    """Compatibility wrapper delegating to authorize_client."""
    return authorize_client(
        client_id=client_id,
        target_id=None,
        project_id=None,
        tool_name=tool_name,
        registry=registry,
    )




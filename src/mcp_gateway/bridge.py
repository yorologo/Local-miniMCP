"""Python Core Bridge for MCP Gateway.

Exposes a CLI interface for the Go MCP adapter to invoke GatewayTools
without reimplementing any policy, SSH transport, or registry logic.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

from . import compatibility
from .policy import authorize_client
from .registry import get_registry
from .tools import GatewayTools

ALLOWED_TOOLS = {
    "health",
    "list_targets",
    "target_status",
    "list_directory",
    "file_stat",
    "read_file",
    "git_status",
    "run_task",
    "write_file",
    "append_file",
    "delete_file",
    "copy_file",
    "move_file",
    "mkdir",
    "search",
    "run_command",
    "gateway_status",
    "gateway_doctor",
    "gateway_backup",
    "gateway_maintenance",
    "gateway_reboot",
}



def get_tools_catalog(client_id: Optional[str] = None, registry: Optional[Any] = None) -> List[str]:
    """Return deterministic alphabetically-sorted catalog of allowlisted tools.

    If client_id is 'NONE' or empty, returns empty list (deny anonymous).
    If client_id is an AI client, filters tools by client authorization.
    If client_id is None or 'local'/'admin', returns full catalog.
    """
    if client_id is not None and str(client_id).strip().upper() in ("NONE", "ANONYMOUS", ""):
        return []

    if client_id and client_id not in ("local", "admin", "system", "test"):
        reg = registry or get_registry()
        allowed = []
        for tool in sorted(list(ALLOWED_TOOLS)):
            ok, _ = authorize_client(client_id, None, None, tool, registry=reg, for_catalog=True)
            if ok:
                allowed.append(tool)
        return allowed

    return sorted(list(ALLOWED_TOOLS))


def invoke_tool(
    tool_name: str,
    args: Dict[str, Any],
    registry: Optional[Any] = None,
    request_id: Optional[str] = None,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Invoke an allowlisted Gateway tool with dictionary arguments."""
    if tool_name not in ALLOWED_TOOLS:
        return {
            "ok": False,
            "tool": tool_name,
            "error": {
                "code": "TOOL_NOT_ALLOWED",
                "message": f"Tool '{tool_name}' is not in the allowlisted gateway tools",
            },
        }

    try:
        reg = registry or get_registry()
        req_id = request_id or args.get("request_id") or args.get("_request_id")
        cli_id = client_id or args.get("client_id") or os.environ.get("MCP_CLIENT_ID", "local")

        # Enforce client authorization
        target_id = args.get("target")
        project_id = args.get("project")
        auth_ok, auth_err = authorize_client(cli_id, target_id, project_id, tool_name, registry=reg)
        if not auth_ok:
            return {
                "ok": False,
                "tool": tool_name,
                "error": {
                    "code": "TOOL_NOT_ALLOWED",
                    "message": auth_err or f"Client '{cli_id}' is not authorized to invoke tool '{tool_name}'",
                },
            }

        gateway = GatewayTools(registry=reg, request_id=req_id, client_id=cli_id)
    except Exception as e:
        return {
            "ok": False,
            "tool": tool_name,
            "error": {
                "code": "CORE_INIT_ERROR",
                "message": f"Failed to initialize gateway core: {e}",
            },
        }

    try:
        if tool_name == "health":
            return gateway.health()

        elif tool_name == "list_targets":
            return gateway.list_targets()

        elif tool_name == "target_status":
            target = args.get("target")
            if not target or not isinstance(target, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required argument 'target'",
                    },
                }
            return gateway.target_status(target)

        elif tool_name == "list_directory":
            target = args.get("target")
            project = args.get("project")
            rel_path = args.get("relative_path", ".")
            if not target or not isinstance(target, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required argument 'target'",
                    },
                }
            if not project or not isinstance(project, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required argument 'project'",
                    },
                }
            return gateway.list_directory(target, project, rel_path)

        elif tool_name == "file_stat":
            target = args.get("target")
            project = args.get("project")
            rel_path = args.get("relative_path")
            if not target or not isinstance(target, str) or not project or not isinstance(project, str) or not rel_path or not isinstance(rel_path, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required arguments: 'target', 'project', and 'relative_path' are required",
                    },
                }
            return gateway.file_stat(target, project, rel_path)

        elif tool_name == "read_file":
            target = args.get("target")
            project = args.get("project")
            rel_path = args.get("relative_path")
            if not target or not isinstance(target, str) or not project or not isinstance(project, str) or not rel_path or not isinstance(rel_path, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required arguments: 'target', 'project', and 'relative_path' are required",
                    },
                }
            return gateway.read_file(target, project, rel_path)

        elif tool_name == "git_status":
            target = args.get("target")
            project = args.get("project")
            if not target or not isinstance(target, str) or not project or not isinstance(project, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required arguments: 'target' and 'project' are required",
                    },
                }
            return gateway.git_status(target, project)

        elif tool_name == "run_task":
            target = args.get("target")
            project = args.get("project")
            task = args.get("task")
            if not target or not isinstance(target, str) or not project or not isinstance(project, str) or not task or not isinstance(task, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required arguments: 'target', 'project', and 'task' are required",
                    },
                }
            return gateway.run_task(target, project, task)

        elif tool_name == "write_file":
            target = args.get("target")
            project = args.get("project")
            rel_path = args.get("relative_path") or args.get("path")
            content = args.get("content")
            expected_sha = args.get("expected_sha256")
            dry_run = bool(args.get("dry_run", False))
            create = bool(args.get("create", False))

            if not target or not isinstance(target, str) or not project or not isinstance(project, str) or not rel_path or not isinstance(rel_path, str) or content is None or not isinstance(content, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required arguments: 'target', 'project', 'relative_path', and 'content' are required",
                    },
                }

            return gateway.write_file(
                target=target,
                project=project,
                relative_path=rel_path,
                content=content,
                expected_sha256=expected_sha,
                dry_run=dry_run,
                create=create,
            )

        elif tool_name == "append_file":
            target = args.get("target")
            project = args.get("project")
            path = args.get("relative_path") or args.get("path")
            content = args.get("content")
            if not target or not isinstance(target, str) or not project or not isinstance(project, str) or not path or not isinstance(path, str) or content is None or not isinstance(content, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required arguments: 'target', 'project', 'path' (or 'relative_path'), and 'content' are required",
                    },
                }
            return gateway.append_file(target=target, project=project, path=path, content=content)

        elif tool_name == "delete_file":
            target = args.get("target")
            project = args.get("project")
            path = args.get("relative_path") or args.get("path")
            if not target or not isinstance(target, str) or not project or not isinstance(project, str) or not path or not isinstance(path, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required arguments: 'target', 'project', and 'path' (or 'relative_path') are required",
                    },
                }
            return gateway.delete_file(target=target, project=project, path=path)

        elif tool_name == "copy_file":
            target = args.get("target")
            project = args.get("project")
            source_path = args.get("source_path")
            dest_path = args.get("dest_path")
            if not target or not isinstance(target, str) or not project or not isinstance(project, str) or not source_path or not isinstance(source_path, str) or not dest_path or not isinstance(dest_path, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required arguments: 'target', 'project', 'source_path', and 'dest_path' are required",
                    },
                }
            return gateway.copy_file(target=target, project=project, source_path=source_path, dest_path=dest_path)

        elif tool_name == "move_file":
            target = args.get("target")
            project = args.get("project")
            source_path = args.get("source_path")
            dest_path = args.get("dest_path")
            if not target or not isinstance(target, str) or not project or not isinstance(project, str) or not source_path or not isinstance(source_path, str) or not dest_path or not isinstance(dest_path, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required arguments: 'target', 'project', 'source_path', and 'dest_path' are required",
                    },
                }
            return gateway.move_file(target=target, project=project, source_path=source_path, dest_path=dest_path)

        elif tool_name == "mkdir":
            target = args.get("target")
            project = args.get("project")
            path = args.get("relative_path") or args.get("path")
            parents = bool(args.get("parents", True))
            if not target or not isinstance(target, str) or not project or not isinstance(project, str) or not path or not isinstance(path, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required arguments: 'target', 'project', and 'path' (or 'relative_path') are required",
                    },
                }
            return gateway.mkdir(target=target, project=project, path=path, parents=parents)

        elif tool_name == "search":
            target = args.get("target")
            project = args.get("project")
            pattern = args.get("pattern")
            path = args.get("relative_path") or args.get("path", ".")
            is_regex = bool(args.get("is_regex", False))
            if not target or not isinstance(target, str) or not project or not isinstance(project, str) or not pattern or not isinstance(pattern, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required arguments: 'target', 'project', and 'pattern' are required",
                    },
                }
            return gateway.search(target=target, project=project, pattern=pattern, path=path, is_regex=is_regex)

        elif tool_name == "run_command":
            target = args.get("target")
            command = args.get("command")
            project = args.get("project")
            cwd = args.get("cwd")
            timeout = args.get("timeout")
            stdin = args.get("stdin")
            env = args.get("env")

            if not target or not isinstance(target, str) or not command or not isinstance(command, str):
                return {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Missing or invalid required arguments: 'target' and 'command' are required",
                    },
                }
            return gateway.run_command(
                target=target,
                command=command,
                project=project,
                cwd=cwd,
                env=env,
                timeout=timeout,
                stdin=stdin,
            )

        elif tool_name == "gateway_status":
            return gateway.gateway_status()

        elif tool_name == "gateway_doctor":
            return gateway.gateway_doctor()

        elif tool_name == "gateway_backup":
            return gateway.gateway_backup()

        elif tool_name == "gateway_maintenance":
            return gateway.gateway_maintenance()

        elif tool_name == "gateway_reboot":
            confirm = bool(args.get("confirm", False))
            return gateway.gateway_reboot(confirm=confirm)

        return {
            "ok": False,
            "tool": tool_name,
            "error": {
                "code": "TOOL_NOT_ALLOWED",
                "message": f"Unhandled tool: {tool_name}",
            },
        }

    except Exception as e:
        return {
            "ok": False,
            "tool": tool_name,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(e),
            },
        }


def main(args_list: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MCP Gateway Python Core Bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    invoke_parser = subparsers.add_parser("invoke", help="Invoke an allowlisted tool")
    invoke_parser.add_argument("tool", help="Tool name to execute")
    invoke_parser.add_argument("args_json", nargs="?", default="{}", help="Tool arguments as JSON string")
    invoke_parser.add_argument("--request-id", dest="request_id", default=None, help="Correlation request ID")
    invoke_parser.add_argument("--client-id", dest="client_id", default=None, help="Client identifier")

    version_parser = subparsers.add_parser("version", help="Output contract versions")
    tools_parser = subparsers.add_parser("tools", help="List available tools")
    tools_parser.add_argument("--client-id", dest="client_id", default=None, help="Client identifier to filter tools")

    parsed = parser.parse_args(args_list)

    if parsed.command == "version":
        info = {
            "ok": True,
            "gateway_version": compatibility.get_gateway_version(),
            "core_api_version": compatibility.get_core_api_version(),
            "bridge_api_version": compatibility.get_bridge_api_version(),
            "tool_catalog_version": compatibility.get_tool_catalog_version(),
            "registry_schema_version": compatibility.get_registry_schema_version(),
            "mcp_protocol": "2026-07-28",
        }
        print(json.dumps(info, indent=2))
        return 0

    if parsed.command == "tools":
        cli_id = getattr(parsed, "client_id", None) or os.environ.get("MCP_CLIENT_ID")
        tools = get_tools_catalog(client_id=cli_id)
        print(json.dumps({"ok": True, "tools": tools}, indent=2))
        return 0

    if parsed.command == "invoke":
        try:
            raw_args = json.loads(parsed.args_json) if parsed.args_json else {}
            if not isinstance(raw_args, dict):
                print(json.dumps({
                    "ok": False,
                    "tool": parsed.tool,
                    "error": {
                        "code": "INVALID_ARGUMENTS",
                        "message": "Tool arguments must be a JSON object",
                    },
                }, indent=2))
                return 1
        except json.JSONDecodeError as e:
            print(json.dumps({
                "ok": False,
                "tool": parsed.tool,
                "error": {
                    "code": "INVALID_ARGUMENTS",
                    "message": f"Malformed JSON arguments: {e}",
                },
            }, indent=2))
            return 1

        result = invoke_tool(
            parsed.tool,
            raw_args,
            request_id=getattr(parsed, "request_id", None),
            client_id=getattr(parsed, "client_id", None),
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())


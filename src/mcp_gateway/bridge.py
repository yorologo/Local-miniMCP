"""Python Core Bridge for MCP Gateway.

Exposes a CLI interface for the Go MCP adapter to invoke GatewayTools
without reimplementing any policy, SSH transport, or registry logic.
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

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
}


def invoke_tool(tool_name: str, args: Dict[str, Any], registry: Optional[Any] = None) -> Dict[str, Any]:
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
        gateway = GatewayTools(registry=reg)
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

    parsed = parser.parse_args(args_list)

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

        result = invoke_tool(parsed.tool, raw_args)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())

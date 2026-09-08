"""Command Line Interface for MCP Gateway."""

import argparse
import json
import os
import sys
from typing import Optional

from .config import GatewayConfig
from .tools import GatewayTools


def main(args_list: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="MCP Gateway CLI - Secure Model Context Protocol Gateway Core"
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        help="Path to targets configuration JSON file",
        default=None,
    )
    parser.add_argument(
        "--registry",
        dest="registry_type",
        choices=["sqlite", "json"],
        help="Registry backend to use (sqlite or json)",
        default=None,
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        help="Path to SQLite database file",
        default=None,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # health
    subparsers.add_parser("health", help="Check gateway health and metadata")

    # list-targets
    subparsers.add_parser("list-targets", help="List configured targets safely")

    # target-status <target>
    p_status = subparsers.add_parser("target-status", help="Check status of a target")
    p_status.add_argument("target", help="Target ID (e.g. termux-main)")

    # list-directory <target> <project> [relative_path]
    p_ls = subparsers.add_parser("list-directory", help="List directory contents")
    p_ls.add_argument("target", help="Target ID")
    p_ls.add_argument("project", help="Project ID")
    p_ls.add_argument("relative_path", nargs="?", default=".", help="Relative path (default: .)")

    # file-stat <target> <project> <relative_path>
    p_stat = subparsers.add_parser("file-stat", help="Get metadata of a file or directory")
    p_stat.add_argument("target", help="Target ID")
    p_stat.add_argument("project", help="Project ID")
    p_stat.add_argument("relative_path", help="Relative path inside project")

    # read-file <target> <project> <relative_path>
    p_read = subparsers.add_parser("read-file", help="Read text file content")
    p_read.add_argument("target", help="Target ID")
    p_read.add_argument("project", help="Project ID")
    p_read.add_argument("relative_path", help="Relative path to text file")

    # git-status <target> <project>
    p_git = subparsers.add_parser("git-status", help="Run 'git status --short' in project root")
    p_git.add_argument("target", help="Target ID")
    p_git.add_argument("project", help="Project ID")

    # run-task <target> <project> <task>
    p_task = subparsers.add_parser("run-task", help="Execute an allowlisted task")
    p_task.add_argument("target", help="Target ID")
    p_task.add_argument("project", help="Project ID")
    p_task.add_argument("task", help="Allowlisted task name")

    parsed = parser.parse_args(args_list)

    try:
        if parsed.registry_type or parsed.db_path or os.environ.get("MCP_GATEWAY_REGISTRY"):
            from .registry import get_registry
            reg = get_registry(backend=parsed.registry_type, config_path=parsed.config_path, db_path=parsed.db_path)
            gateway = GatewayTools(registry=reg)
        elif parsed.config_path:
            config = GatewayConfig.load(parsed.config_path)
            gateway = GatewayTools(config=config)
        else:
            from .registry import get_registry
            reg = get_registry(config_path=parsed.config_path, db_path=parsed.db_path)
            gateway = GatewayTools(registry=reg)
    except Exception as e:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "CONFIG_ERROR",
                "message": str(e),
            }
        }, indent=2))
        return 1

    result = {}
    if parsed.command == "health":
        result = gateway.health()
    elif parsed.command == "list-targets":
        result = gateway.list_targets()
    elif parsed.command == "target-status":
        result = gateway.target_status(parsed.target)
    elif parsed.command == "list-directory":
        result = gateway.list_directory(parsed.target, parsed.project, parsed.relative_path)
    elif parsed.command == "file-stat":
        result = gateway.file_stat(parsed.target, parsed.project, parsed.relative_path)
    elif parsed.command == "read-file":
        result = gateway.read_file(parsed.target, parsed.project, parsed.relative_path)
    elif parsed.command == "git-status":
        result = gateway.git_status(parsed.target, parsed.project)
    elif parsed.command == "run-task":
        result = gateway.run_task(parsed.target, parsed.project, parsed.task)

    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())

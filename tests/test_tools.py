import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

try:
    from mcp_gateway.config import GatewayConfig
    from mcp_gateway.ssh_transport import SSHTransportResult
    from mcp_gateway.tools import GatewayTools
except ImportError:
    from src.mcp_gateway.config import GatewayConfig
    from src.mcp_gateway.ssh_transport import SSHTransportResult
    from src.mcp_gateway.tools import GatewayTools


class DummyTransport:
    """Mock SSH transport for deterministic unit testing."""

    def __init__(self):
        self.cmd_responses = {}
        self.canonical_responses = {}
        self.file_responses = {}

    def run_command(self, target, remote_cmd, timeout=None, cwd=None):
        if "hostname" in remote_cmd:
            return SSHTransportResult(0, "mock-host\n", "", 15)
        if "git status" in remote_cmd:
            return SSHTransportResult(0, " M README.md\n", "", 25)
        if "argv_test" in remote_cmd:
            return SSHTransportResult(0, "task output\n", "", 30)
        return SSHTransportResult(0, "", "", 10)

    def resolve_canonical_path(self, target, candidate_path, timeout=10):
        if "evil" in candidate_path or "escape" in candidate_path:
            return "/outside/path/evil.txt"
        return candidate_path

    def read_remote_file_content(self, target, canonical_path, max_bytes=None):
        return "MOCK FILE CONTENT"


class TestGatewayTools(unittest.TestCase):

    def setUp(self):
        self.test_data = {
            "targets": {
                "mock-target": {
                    "platform": "linux",
                    "host": "127.0.0.1",
                    "port": 22,
                    "user": "tester",
                    "ssh_alias": "mock-alias",
                    "enabled": True,
                    "projects": {
                        "mock-proj": {
                            "root": "/home/tester/proj",
                            "read": True,
                            "write": False,
                            "tasks": {
                                "status": {
                                    "enabled": True,
                                    "argv": ["echo", "argv_test"],
                                    "timeout": 15,
                                }
                            }
                        }
                    }
                }
            }
        }
        self.config = GatewayConfig(raw_data=self.test_data)
        self.transport = DummyTransport()
        self.tools = GatewayTools(config=self.config, transport=self.transport)

    def test_health_structure(self):
        res = self.tools.health()
        self.assertTrue(res["ok"])
        self.assertEqual(res["tool"], "health")
        self.assertIn("gateway_status", res["result"])
        self.assertIn("python_version", res["result"])
        self.assertEqual(res["result"]["configured_targets"], 1)

    def test_list_targets_structure(self):
        res = self.tools.list_targets()
        self.assertTrue(res["ok"])
        self.assertEqual(res["tool"], "list_targets")
        targets = res["result"]["targets"]
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["id"], "mock-target")

    def test_target_status(self):
        res = self.tools.target_status("mock-target")
        self.assertTrue(res["ok"])
        self.assertEqual(res["tool"], "target_status")
        self.assertTrue(res["result"]["reachable"])
        self.assertEqual(res["result"]["remote_hostname"], "mock-host")

    def test_unknown_target_returns_error(self):
        res = self.tools.target_status("nonexistent")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "UNKNOWN_TARGET")

    def test_unknown_project_returns_error(self):
        res = self.tools.read_file("mock-target", "nonexistent-proj", "test.txt")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "UNKNOWN_PROJECT")

    def test_parent_traversal_rejected(self):
        res = self.tools.read_file("mock-target", "mock-proj", "../etc/passwd")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "INVALID_PATH")

    def test_absolute_path_rejected(self):
        res = self.tools.read_file("mock-target", "mock-proj", "/etc/passwd")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "INVALID_PATH")

    def test_symlink_escape_rejected(self):
        res = self.tools.read_file("mock-target", "mock-proj", "evil-link.txt")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "PATH_OUTSIDE_ALLOWED_ROOT")

    def test_git_status_allowed(self):
        res = self.tools.git_status("mock-target", "mock-proj")
        self.assertTrue(res["ok"])
        self.assertIn("status_output", res["result"])

    def test_run_task_allowed(self):
        res = self.tools.run_task("mock-target", "mock-proj", "status")
        self.assertTrue(res["ok"])
        self.assertEqual(res["result"]["task"], "status")
        self.assertEqual(res["result"]["exit_code"], 0)

    def test_arbitrary_task_denied(self):
        res = self.tools.run_task("mock-target", "mock-proj", "arbitrary_cmd")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "TASK_NOT_ALLOWED")


if __name__ == "__main__":
    unittest.main()

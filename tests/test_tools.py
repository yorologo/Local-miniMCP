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

    def run_command(self, target, remote_cmd, timeout=None, cwd=None, **kwargs):
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

    def probe_remote_path(self, target, candidate_path, timeout=10):
        import hashlib
        if "symlink" in candidate_path:
            return {
                "exists": True, "is_symlink": True, "is_file": False, "is_dir": False,
                "canonical_path": candidate_path, "parent_exists": True, "parent_is_symlink": False,
                "parent_canonical_path": os.path.dirname(candidate_path), "sha256": "", "size": 0, "content": ""
            }
        if "existing.txt" in candidate_path:
            content = "hello existing\n"
            sha = hashlib.sha256(content.encode()).hexdigest()
            return {
                "exists": True, "is_symlink": False, "is_file": True, "is_dir": False,
                "canonical_path": candidate_path, "parent_exists": True, "parent_is_symlink": False,
                "parent_canonical_path": os.path.dirname(candidate_path), "sha256": sha, "size": len(content), "content": content
            }
        return {
            "exists": False, "is_symlink": False, "is_file": False, "is_dir": False,
            "canonical_path": "", "parent_exists": True, "parent_is_symlink": False,
            "parent_canonical_path": os.path.dirname(candidate_path), "sha256": "", "size": 0, "content": ""
        }

    def write_remote_file_atomic(self, target, dest_path, content_bytes, create, expected_sha256=None, backup_dir=None, max_write_bytes=262144, timeout=20):
        import hashlib
        sha = hashlib.sha256(content_bytes).hexdigest()
        return {
            "ok": True,
            "created": create,
            "old_sha256": expected_sha256,
            "new_sha256": sha,
            "bytes_written": len(content_bytes),
            "atomic": True
        }



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


    def test_read_file_includes_sha256(self):
        res = self.tools.read_file("mock-target", "mock-proj", "hello.txt")
        self.assertTrue(res["ok"])
        self.assertIn("sha256", res["result"])
        self.assertEqual(len(res["result"]["sha256"]), 64)

    def test_write_file_writes_globally_disabled(self):
        # By default, writes_enabled is false
        res = self.tools.write_file("mock-target", "mock-proj", "new.txt", "hello", create=True)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "WRITES_DISABLED")

    def test_write_file_project_write_disabled(self):
        # Mock writes_enabled
        self.tools._is_writes_enabled = lambda: True

        # Project mock-proj has write: False
        res = self.tools.write_file("mock-target", "mock-proj", "new.txt", "hello", create=True)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "WRITE_NOT_ALLOWED")

    def test_write_file_dry_run_and_create(self):
        self.tools._is_writes_enabled = lambda: True
        self.config._data["targets"]["mock-target"]["projects"]["mock-proj"]["write"] = True

        # Dry run on new file
        res = self.tools.write_file("mock-target", "mock-proj", "new.txt", "hello new\n", dry_run=True, create=True)
        self.assertTrue(res["ok"])
        self.assertTrue(res["result"]["dry_run"])
        self.assertEqual(res["result"]["size_before"], 0)
        self.assertEqual(res["result"]["size_after"], 10)
        self.assertIn("diff_truncated", res["result"])

        # Real create on new file
        res = self.tools.write_file("mock-target", "mock-proj", "new.txt", "hello new\n", create=True)
        self.assertTrue(res["ok"])
        self.assertTrue(res["result"]["created"])
        self.assertEqual(res["result"]["bytes_written"], 10)

    def test_write_file_overwrite_with_sha(self):
        import hashlib
        self.tools._is_writes_enabled = lambda: True
        self.config._data["targets"]["mock-target"]["projects"]["mock-proj"]["write"] = True

        existing_sha = hashlib.sha256(b"hello existing\n").hexdigest()

        # Overwrite with wrong sha
        res = self.tools.write_file("mock-target", "mock-proj", "existing.txt", "new data", expected_sha256="wronghash")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "WRITE_CONFLICT")

        # Overwrite without sha
        res = self.tools.write_file("mock-target", "mock-proj", "existing.txt", "new data")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "WRITE_CONFLICT")

        # Overwrite with correct sha
        res = self.tools.write_file("mock-target", "mock-proj", "existing.txt", "new data", expected_sha256=existing_sha)
        self.assertTrue(res["ok"])
        self.assertFalse(res["result"]["created"])

    def test_write_file_negative_cases(self):
        self.tools._is_writes_enabled = lambda: True
        self.config._data["targets"]["mock-target"]["projects"]["mock-proj"]["write"] = True

        # Traversal
        res = self.tools.write_file("mock-target", "mock-proj", "../etc/passwd", "evil")
        self.assertEqual(res["error"]["code"], "INVALID_PATH")

        # Absolute path
        res = self.tools.write_file("mock-target", "mock-proj", "/etc/passwd", "evil")
        self.assertEqual(res["error"]["code"], "INVALID_PATH")

        # Symlink target
        res = self.tools.write_file("mock-target", "mock-proj", "symlink_file.txt", "evil")
        self.assertEqual(res["error"]["code"], "SYMLINK_WRITE_DENIED")

        # NUL byte in content
        res = self.tools.write_file("mock-target", "mock-proj", "bad.txt", "bad\0content", create=True)
        self.assertEqual(res["error"]["code"], "INVALID_ENCODING")


if __name__ == "__main__":
    unittest.main()


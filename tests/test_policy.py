import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

try:
    from mcp_gateway.policy import (
        PolicyError,
        check_capability,
        validate_canonical_path,
        validate_relative_path,
        validate_task,
    )
except ImportError:
    from src.mcp_gateway.policy import (
        PolicyError,
        check_capability,
        validate_canonical_path,
        validate_relative_path,
        validate_task,
    )


class TestPolicy(unittest.TestCase):

    def test_valid_relative_paths(self):
        self.assertEqual(validate_relative_path("."), ".")
        self.assertEqual(validate_relative_path("file.txt"), "file.txt")
        self.assertEqual(validate_relative_path("src/main.py"), "src/main.py")
        self.assertEqual(validate_relative_path("src/sub/deep.txt"), "src/sub/deep.txt")

    def test_absolute_paths_rejected(self):
        for bad_path in ["/etc/passwd", "/root", "\\Windows\\System32", "C:\\boot.ini", "~/keys"]:
            with self.subTest(bad_path=bad_path):
                with self.assertRaises(PolicyError) as ctx:
                    validate_relative_path(bad_path)
                self.assertEqual(ctx.exception.code, "INVALID_PATH")

    def test_traversal_paths_rejected(self):
        for bad_path in ["..", "../", "../foo", "foo/..", "foo/../../bar", "a/../b/../../c"]:
            with self.subTest(bad_path=bad_path):
                with self.assertRaises(PolicyError) as ctx:
                    validate_relative_path(bad_path)
                self.assertEqual(ctx.exception.code, "INVALID_PATH")

    def test_empty_and_nul_paths_rejected(self):
        for bad_path in ["", "   ", "foo\0bar"]:
            with self.subTest(bad_path=bad_path):
                with self.assertRaises(PolicyError) as ctx:
                    validate_relative_path(bad_path)
                self.assertEqual(ctx.exception.code, "INVALID_PATH")

    def test_canonical_root_match(self):
        root = "/data/projects/myproj"
        # Exact root
        validate_canonical_path("/data/projects/myproj", root)
        # Inside root
        validate_canonical_path("/data/projects/myproj/src/main.py", root)

    def test_sibling_prefix_escape_rejected(self):
        root = "/data/projects/myproj"
        evil_sibling = "/data/projects/myproj-evil/hack.txt"
        with self.assertRaises(PolicyError) as ctx:
            validate_canonical_path(evil_sibling, root)
        self.assertEqual(ctx.exception.code, "PATH_OUTSIDE_ALLOWED_ROOT")

    def test_canonical_traversal_escape_rejected(self):
        root = "/data/projects/myproj"
        outside_path = "/data/projects/other/secret.txt"
        with self.assertRaises(PolicyError) as ctx:
            validate_canonical_path(outside_path, root)
        self.assertEqual(ctx.exception.code, "PATH_OUTSIDE_ALLOWED_ROOT")

    def test_check_capability_read(self):
        proj_ok = {"read": True, "write": False}
        proj_no = {"read": False, "write": False}
        check_capability(proj_ok, "read")
        with self.assertRaises(PolicyError) as ctx:
            check_capability(proj_no, "read")
        self.assertEqual(ctx.exception.code, "TOOL_NOT_ALLOWED")

    def test_validate_task_allowlisted(self):
        proj = {
            "tasks": {
                "git_status": {
                    "enabled": True,
                    "argv": ["git", "status", "--short"],
                    "timeout": 20,
                }
            }
        }
        res = validate_task(proj, "git_status")
        self.assertEqual(res["argv"], ["git", "status", "--short"])
        self.assertEqual(res["timeout"], 20)

    def test_validate_task_arbitrary_rejected(self):
        proj = {"tasks": {}}
        with self.assertRaises(PolicyError) as ctx:
            validate_task(proj, "rm -rf /")
        self.assertEqual(ctx.exception.code, "TASK_NOT_ALLOWED")


if __name__ == "__main__":
    unittest.main()

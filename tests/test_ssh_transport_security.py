import os
import subprocess
import tempfile
import unittest

from mcp_gateway.ssh_transport import SSHError, SSHTransport, SSHTransportResult


class LocalProbeTransport(SSHTransport):
    def __init__(self):
        pass

    def run_command(self, target, remote_cmd, timeout=None, cwd=None, **kwargs):
        proc = subprocess.run(
            remote_cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout or 10,
        )
        return SSHTransportResult(proc.returncode, proc.stdout, proc.stderr, 0)


class TestSafeDestinationResolution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "project")
        self.outside = os.path.join(self.tmp.name, "outside")
        os.makedirs(self.root)
        os.makedirs(self.outside)
        self.transport = LocalProbeTransport()
        self.target = {"id": "local-test"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_nested_symlink_parent_escape_is_denied(self):
        safe_parent = os.path.join(self.root, "safe")
        os.makedirs(safe_parent)
        os.symlink(self.outside, os.path.join(safe_parent, "escape"))
        candidate = os.path.join(safe_parent, "escape", "new.txt")
        with self.assertRaises(SSHError) as ctx:
            self.transport.resolve_safe_destination(self.target, self.root, candidate)
        self.assertEqual(ctx.exception.code, "PATH_OUTSIDE_ALLOWED_ROOT")

    def test_existing_symlink_destination_is_denied(self):
        outside_file = os.path.join(self.outside, "secret.txt")
        with open(outside_file, "w", encoding="utf-8") as fh:
            fh.write("secret")
        link = os.path.join(self.root, "link.txt")
        os.symlink(outside_file, link)
        with self.assertRaises(SSHError) as ctx:
            self.transport.resolve_safe_destination(self.target, self.root, link)
        self.assertEqual(ctx.exception.code, "SYMLINK_WRITE_DENIED")

    def test_missing_child_beneath_safe_parent_is_allowed(self):
        parent = os.path.join(self.root, "safe")
        os.makedirs(parent)
        dest = os.path.join(parent, "new.txt")
        resolved = self.transport.resolve_safe_destination(self.target, self.root, dest)
        self.assertEqual(resolved["destination_path"], dest)
        self.assertFalse(resolved["exists"])

    def test_mkdir_missing_parents_stays_under_root(self):
        dest = os.path.join(self.root, "a", "b", "c")
        resolved = self.transport.resolve_safe_destination(
            self.target, self.root, dest, allow_missing_parents=True
        )
        self.assertEqual(resolved["destination_path"], dest)


if __name__ == "__main__":
    unittest.main()

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from mcp_gateway.admin_cli import set_password_cmd
from mcp_gateway.cli_unified import cmd_rollback, cmd_setup, cmd_update
from mcp_gateway.registry import SQLiteRegistry


class TestCliReleaseUX(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "gateway.db")
        self.env = mock.patch.dict(os.environ, {"MCP_GATEWAY_DB": self.db, "MCP_GATEWAY_REGISTRY": "sqlite"})
        self.env.start()
        SQLiteRegistry(self.db)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_setup_noninteractive_requires_admin_password(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO("")), redirect_stdout(stdout), redirect_stderr(stderr):
            rc = cmd_setup()
        self.assertEqual(rc, 2)
        self.assertIn("No Admin password is configured", stderr.getvalue())

    def test_setup_password_stdin_bootstraps_admin_and_runs_doctor(self):
        stdin = io.StringIO("correct-horse-battery-staple\n")
        stdout = io.StringIO()
        with mock.patch("sys.stdin", stdin), mock.patch("mcp_gateway.cli_unified.cmd_doctor", return_value=0), redirect_stdout(stdout):
            rc = cmd_setup(password_stdin=True)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(SQLiteRegistry(self.db).get_admin_user("admin"))
        self.assertIn("Setup baseline complete", stdout.getvalue())

    def test_setup_preserves_existing_admin_password(self):
        self.assertEqual(set_password_cmd("admin", self.db, password="existing-password"), 0)
        before = SQLiteRegistry(self.db).get_admin_user("admin")["password_hash"]
        with mock.patch("mcp_gateway.cli_unified.cmd_doctor", return_value=0):
            rc = cmd_setup()
        after = SQLiteRegistry(self.db).get_admin_user("admin")["password_hash"]
        self.assertEqual(rc, 0)
        self.assertEqual(before, after)

    def test_update_and_rollback_point_to_supported_root_path(self):
        out = io.StringIO()
        with redirect_stdout(out):
            update_rc = cmd_update()
            rollback_rc = cmd_rollback()
        self.assertEqual(update_rc, 2)
        self.assertEqual(rollback_rc, 2)
        text = out.getvalue()
        self.assertIn("sudo ./install.sh", text)
        self.assertIn("install.sh --rollback", text)
        self.assertIn("run-resumable.sh", text)
        self.assertIn("DEPLOYMENT_VERIFIED", text)
        self.assertIn("scripts/deploy-pi.sh <exact-sha>", text)


if __name__ == "__main__":
    unittest.main()

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from werkzeug.security import generate_password_hash
from mcp_gateway.registry import SQLiteRegistry
from mcp_gateway.ssh_transport import SSHTransportResult
from mcp_gateway.tools import GatewayTools
from mcp_gateway.web import create_app


class MockTransport:
    def run_command(self, target, remote_cmd, timeout=None, cwd=None):
        return SSHTransportResult(0, "mock-host\n", "", 10)

    def resolve_canonical_path(self, target, candidate_path, timeout=10):
        return candidate_path


class TestWebViews(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "web_views_test.db")
        self.registry = SQLiteRegistry(self.db_path)
        self.registry.set_admin_password("admin", generate_password_hash("Password123!"))

        # Seed a target and a project
        self.registry.add_target({
            "id": "t1",
            "display_name": "Target 1",
            "platform": "linux",
            "host": "192.168.1.50",
            "port": 22,
            "user": "worker",
            "enabled": True,
        })
        self.registry.add_project("t1", {
            "id": "p1",
            "display_name": "Project 1",
            "root": "/srv/app",
            "read": True,
            "enabled": True,
        })

        self.tools = GatewayTools(registry=self.registry, transport=MockTransport())
        self.app = create_app(
            registry=self.registry,
            tools=self.tools,
            secret_key="test-key-views",
            test_config={"TESTING": True},
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["user"] = "admin"
            sess["last_active"] = time.time()
            sess["csrf_token"] = "valid-token"

    def test_dashboard_view(self):
        self._login()
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"System Dashboard", res.data)
        self.assertIn(b"Targets Online", res.data)

    def test_targets_crud(self):
        self._login()
        # 1. List targets
        res = self.client.get("/targets")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"t1", res.data)

        # 2. Add target form
        res_form = self.client.get("/targets/add")
        self.assertEqual(res_form.status_code, 200)

        # 3. Add target POST
        res_add = self.client.post(
            "/targets/add",
            data={
                "id": "t2",
                "display_name": "Target 2",
                "platform": "linux",
                "host": "192.168.1.51",
                "port": "22",
                "user": "worker2",
                "enabled": "on",
                "csrf_token": "valid-token",
            },
            follow_redirects=True,
        )
        self.assertEqual(res_add.status_code, 200)
        self.assertIn(b"t2", res_add.data)

        # 4. Edit target POST
        res_edit = self.client.post(
            "/targets/t2/edit",
            data={
                "display_name": "Target 2 Updated",
                "platform": "linux",
                "host": "192.168.1.52",
                "port": "2222",
                "user": "worker2_new",
                "enabled": "on",
                "csrf_token": "valid-token",
            },
            follow_redirects=True,
        )
        self.assertEqual(res_edit.status_code, 200)
        t2 = self.registry.get_target("t2")
        self.assertEqual(t2["host"], "192.168.1.52")

        # 5. Toggle target
        res_toggle = self.client.post(
            "/targets/t2/toggle",
            data={"csrf_token": "valid-token"},
            follow_redirects=True,
        )
        self.assertEqual(res_toggle.status_code, 200)
        self.assertIn(b"DISABLED", res_toggle.data)

        # 6. Test target
        res_test = self.client.post(
            "/targets/t1/test",
            data={"csrf_token": "valid-token"},
            follow_redirects=True,
        )
        self.assertEqual(res_test.status_code, 200)
        self.assertIn(b"reachable", res_test.data)

    def test_projects_crud(self):
        self._login()
        # 1. List projects
        res = self.client.get("/projects")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"p1", res.data)

        # 2. Add project
        res_add = self.client.post(
            "/projects/add",
            data={
                "target_id": "t1",
                "id": "p2",
                "display_name": "Project 2",
                "root": "/srv/p2",
                "read": "on",
                "enabled": "on",
                "csrf_token": "valid-token",
            },
            follow_redirects=True,
        )
        self.assertEqual(res_add.status_code, 200)
        p2 = self.registry.get_project("t1", "p2")
        self.assertEqual(p2["root"], "/srv/p2")

        # 3. Toggle project enabled -> disabled
        res_toggle = self.client.post(
            "/projects/t1/p2/toggle",
            data={"csrf_token": "valid-token"},
            follow_redirects=True,
        )
        self.assertEqual(res_toggle.status_code, 200)
        self.assertIn(b"disabled", res_toggle.data)

        # Re-enable p2
        self.client.post(
            "/projects/t1/p2/toggle",
            data={"csrf_token": "valid-token"},
            follow_redirects=True,
        )

        # 4. Toggle project write capability
        self.assertFalse(self.registry.get_project("t1", "p2").get("write", False))
        res_toggle_write = self.client.post(
            "/projects/t1/p2/toggle-write",
            data={"csrf_token": "valid-token"},
            follow_redirects=True,
        )
        self.assertEqual(res_toggle_write.status_code, 200)
        self.assertTrue(self.registry.get_project("t1", "p2").get("write", False))
        self.assertIn(b"WRITE \xe2\x9c\x93", res_toggle_write.data)  # WRITE ✓

        # 5. Revoke write capability
        res_revoke = self.client.post(
            "/projects/t1/p2/toggle-write",
            data={"csrf_token": "valid-token"},
            follow_redirects=True,
        )
        self.assertEqual(res_revoke.status_code, 200)
        self.assertFalse(self.registry.get_project("t1", "p2").get("write", False))

    def test_clients_crud(self):
        self._login()
        # 1. Add AI Client
        res_add = self.client.post(
            "/clients/add",
            data={
                "id": "gemini-client",
                "display_name": "Gemini Assistant",
                "provider": "Google",
                "protocol": "mcp",
                "enabled": "on",
                "notes": "Primary agent client",
                "csrf_token": "valid-token",
            },
            follow_redirects=True,
        )
        self.assertEqual(res_add.status_code, 200)
        client = self.registry.get_client("gemini-client")
        self.assertEqual(client["display_name"], "Gemini Assistant")

        # 2. Toggle AI Client
        res_toggle = self.client.post(
            "/clients/gemini-client/toggle",
            data={"csrf_token": "valid-token"},
            follow_redirects=True,
        )
        self.assertEqual(res_toggle.status_code, 200)
        client_after = self.registry.get_client("gemini-client")
        self.assertFalse(client_after["enabled"])

    def test_activity_view(self):
        self._login()
        self.registry.record_activity({"action": "sample_tool_run", "target_id": "t1", "success": True})
        res = self.client.get("/activity")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"sample_tool_run", res.data)

    def test_system_view(self):
        self._login()
        res = self.client.get("/system")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Gateway Runtime", res.data)
        self.assertIn(b"SQLiteRegistry", res.data)

    def test_settings_view_and_update(self):
        self._login()
        res = self.client.get("/settings")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Emergency Kill Switch", res.data)

        # Update valid settings
        res_post = self.client.post(
            "/settings",
            data={
                "default_timeout": "45",
                "max_output_bytes": "524288",
                "max_file_read_bytes": "2097152",
                "activity_retention": "2000",
                "csrf_token": "valid-token",
            },
            follow_redirects=True,
        )
        self.assertEqual(res_post.status_code, 200)
        self.assertEqual(self.registry.get_setting("default_timeout"), "45")

        # Range validation rejection
        res_invalid = self.client.post(
            "/settings",
            data={
                "default_timeout": "9999",  # exceeds max 300
                "max_output_bytes": "524288",
                "max_file_read_bytes": "2097152",
                "activity_retention": "2000",
                "csrf_token": "valid-token",
            },
            follow_redirects=True,
        )
        self.assertEqual(res_invalid.status_code, 200)
        self.assertIn(b"Timeout must be between", res_invalid.data)

        # Toggle writes switch (enable)
        self.assertEqual(self.registry.get_setting("writes_enabled"), "false")
        res_toggle_writes = self.client.post(
            "/settings/toggle-writes",
            data={"csrf_token": "valid-token"},
            follow_redirects=True,
        )
        self.assertEqual(res_toggle_writes.status_code, 200)
        self.assertEqual(self.registry.get_setting("writes_enabled"), "true")

        # Disable writes panic button
        res_panic = self.client.post(
            "/settings/disable-writes",
            data={"csrf_token": "valid-token"},
            follow_redirects=True,
        )
        self.assertEqual(res_panic.status_code, 200)
        self.assertEqual(self.registry.get_setting("writes_enabled"), "false")
        self.assertIn(b"Controlled writes have been immediately DISABLED", res_panic.data)


if __name__ == "__main__":
    unittest.main()

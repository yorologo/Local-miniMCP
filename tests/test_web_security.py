import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from werkzeug.security import generate_password_hash
from mcp_gateway.registry import SQLiteRegistry
from mcp_gateway.web import create_app


class TestWebSecurity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "web_sec_test.db")
        self.registry = SQLiteRegistry(self.db_path)
        self.registry.set_admin_password("admin", generate_password_hash("Password123!"))

        self.app = create_app(
            registry=self.registry,
            secret_key="test-secret-key-security",
            test_config={"TESTING": True},
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["user"] = "admin"
            sess["last_active"] = time.time()
            sess["csrf_token"] = "valid-csrf-token"

    def test_security_headers(self):
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)

        # Check required security headers
        self.assertIn("Content-Security-Policy", res.headers)
        self.assertIn("default-src 'self'", res.headers["Content-Security-Policy"])
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(res.headers.get("Referrer-Policy"), "no-referrer")
        self.assertEqual(res.headers.get("Permissions-Policy"), "camera=(), microphone=(), geolocation=()")
        csp = res.headers["Content-Security-Policy"]
        self.assertIn("script-src 'self'", csp)
        self.assertIn("style-src 'self'", csp)
        self.assertNotIn("'unsafe-inline'", csp)
        self.assertIn("no-store", res.headers.get("Cache-Control", ""))

    def test_untrusted_host_is_rejected(self):
        res = self.client.get("/login", headers={"Host": "evil.example"})
        self.assertEqual(res.status_code, 403)

    def test_explicit_lan_host_can_be_allowlisted(self):
        self.app.config["ADMIN_ALLOWED_HOSTS"] = {"127.0.0.1", "localhost", "192.168.68.55"}
        res = self.client.get("/login", headers={"Host": "192.168.68.55"})
        self.assertEqual(res.status_code, 200)

    def test_production_admin_service_uses_ipv4_wildcard_bind(self):
        unit_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "config", "systemd", "mcp-gateway-admin.service")
        )
        with open(unit_path, "r", encoding="utf-8") as f:
            unit = f.read()
        self.assertIn("Environment=MCP_ADMIN_HOST=0.0.0.0", unit)
        self.assertIn("Environment=MCP_ADMIN_PORT=80", unit)
        self.assertIn("Environment=MCP_ADMIN_ALLOWED_HOSTS=127.0.0.1,localhost,192.168.68.55,mcp-pi", unit)
        self.assertIn("User=mcp-gateway", unit)
        self.assertIn("Group=mcp-gateway", unit)
        self.assertIn("CapabilityBoundingSet=CAP_NET_BIND_SERVICE", unit)
        self.assertIn("AmbientCapabilities=CAP_NET_BIND_SERVICE", unit)
        self.assertIn("NoNewPrivileges=true", unit)

    def test_csrf_missing_denied(self):
        self._login()
        # Attempt POST without csrf_token
        res = self.client.post("/settings/kill-switch", data={})
        self.assertEqual(res.status_code, 403)

    def test_csrf_invalid_denied(self):
        self._login()
        # Attempt POST with wrong csrf_token
        res = self.client.post("/settings/kill-switch", data={"csrf_token": "attacker-token"})
        self.assertEqual(res.status_code, 403)

    def test_csrf_valid_permitted(self):
        self._login()
        # POST with valid csrf_token
        res = self.client.post("/settings/kill-switch", data={"csrf_token": "valid-csrf-token"})
        self.assertEqual(res.status_code, 302)

    def test_get_mutation_denied(self):
        self._login()
        # Trying to toggle kill switch via GET should return 405 Method Not Allowed
        res = self.client.get("/settings/kill-switch")
        self.assertEqual(res.status_code, 405)

        # Trying to toggle a target via GET should return 405
        res_target = self.client.get("/targets/t1/toggle")
        self.assertEqual(res_target.status_code, 405)

    def test_xss_escaping(self):
        self._login()
        # Add target with script tag in display_name
        xss_payload = "<script>alert('xss')</script>"
        res = self.client.post(
            "/targets/add",
            data={
                "id": "xss-test",
                "display_name": xss_payload,
                "platform": "linux",
                "host": "localhost",
                "port": "22",
                "user": "root",
                "enabled": "on",
                "csrf_token": "valid-csrf-token",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        # Verify script tag is HTML-escaped, never raw
        self.assertNotIn(b"<script>alert('xss')</script>", res.data)
        self.assertIn(b"&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;", res.data)

    def test_sql_injection_harmless(self):
        self._login()
        # Attempt SQL injection in target creation
        sqli_id = "sqli' OR '1'='1"
        res = self.client.post(
            "/targets/add",
            data={
                "id": sqli_id,
                "display_name": "SQLi Test",
                "platform": "linux",
                "host": "localhost",
                "port": "22",
                "user": "root",
                "enabled": "on",
                "csrf_token": "valid-csrf-token",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)

        # The ID should be treated literally as a string, not as SQL
        target = self.registry.get_target(sqli_id)
        self.assertEqual(target["host"], "localhost")


if __name__ == "__main__":
    unittest.main()

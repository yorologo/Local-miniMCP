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
from mcp_gateway.web.auth import _FAILED_LOGINS


class TestWebAuth(unittest.TestCase):
    def setUp(self):
        _FAILED_LOGINS.clear()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "web_auth_test.db")
        self.registry = SQLiteRegistry(self.db_path)
        self.registry.set_admin_password("admin", generate_password_hash("CorrectPassword123!"))

        self.app = create_app(
            registry=self.registry,
            secret_key="test-secret-key",
            test_config={"TESTING": True},
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()
        _FAILED_LOGINS.clear()

    def test_unauthenticated_redirects_to_login(self):
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers["Location"])

    def test_login_success(self):
        # Fetch login page to get CSRF token
        login_page = self.client.get("/login")
        self.assertEqual(login_page.status_code, 200)

        with self.client.session_transaction() as sess:
            token = sess["csrf_token"]

        res = self.client.post(
            "/login",
            data={"username": "admin", "password": "CorrectPassword123!", "csrf_token": token},
            follow_redirects=False,
        )
        self.assertEqual(res.status_code, 302)
        self.assertIn("/dashboard", res.headers["Location"])

        # Session should contain user
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user"), "admin")

        # Access dashboard should now be 200
        dash = self.client.get("/dashboard")
        self.assertEqual(dash.status_code, 200)
        self.assertIn(b"System Dashboard", dash.data)

    def test_login_failure_bad_password(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "valid-token"

        res = self.client.post(
            "/login",
            data={"username": "admin", "password": "WrongPassword", "csrf_token": "valid-token"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertIn(b"Invalid username or password", res.data)

    def test_login_rate_limiting(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "valid-token"

        # 5 consecutive failed attempts
        for _ in range(5):
            self.client.post(
                "/login",
                data={"username": "admin", "password": "WrongPassword", "csrf_token": "valid-token"},
            )

        # 6th attempt should be locked out with 429
        res = self.client.post(
            "/login",
            data={"username": "admin", "password": "CorrectPassword123!", "csrf_token": "valid-token"},
        )
        self.assertEqual(res.status_code, 429)
        self.assertIn(b"Too many failed login attempts", res.data)

    def test_logout(self):
        # Log in
        with self.client.session_transaction() as sess:
            sess["user"] = "admin"
            sess["last_active"] = time.time()
            sess["csrf_token"] = "test-token"

        # POST logout with CSRF
        res = self.client.post("/logout", data={"csrf_token": "test-token"})
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers["Location"])

        # User should no longer be logged in
        dash = self.client.get("/dashboard")
        self.assertEqual(dash.status_code, 302)
        self.assertIn("/login", dash.headers["Location"])


if __name__ == "__main__":
    unittest.main()

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mcp_gateway.bridge import invoke_tool, get_tools_catalog
from mcp_gateway.policy import authorize_client, TOOL_CAPABILITIES
from mcp_gateway.tools import GatewayTools


class TestApplianceTools(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mcp_test_appliance_")
        self.db_path = os.path.join(self.temp_dir, "gateway.db")

        # Create mock registry
        self.mock_registry = MagicMock()
        self.mock_registry.db_path = self.db_path
        self.mock_registry.target_count = 1
        self.mock_registry.get_setting.side_effect = lambda k, d=None: {
            "gateway_enabled": "true",
            "writes_enabled": "false",
        }.get(k, d)

        # AI Clients
        self.mock_registry.get_client.side_effect = lambda cid: {
            "id": cid,
            "display_name": cid,
            "enabled": True,
        }

        # Client grants: admin-client has admin, readonly-client has read
        def mock_get_client_grants(cid):
            if cid == "admin-client":
                return [{"capability": "admin", "target_id": "*", "project_id": "*", "enabled": True}]
            elif cid == "readonly-client":
                return [{"capability": "read", "target_id": "*", "project_id": "*", "enabled": True}]
            return []

        self.mock_registry.get_client_grants.side_effect = mock_get_client_grants

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tool_catalog_contains_appliance_tools(self):
        cat = get_tools_catalog()
        expected = [
            "gateway_backup",
            "gateway_doctor",
            "gateway_maintenance",
            "gateway_reboot",
            "gateway_status",
        ]
        for t in expected:
            self.assertIn(t, cat)

    def test_readonly_client_catalog_excludes_appliance_tools(self):
        cat = get_tools_catalog(client_id="readonly-client", registry=self.mock_registry)
        expected = [
            "gateway_backup",
            "gateway_doctor",
            "gateway_maintenance",
            "gateway_reboot",
            "gateway_status",
        ]
        for t in expected:
            self.assertNotIn(t, cat)

    def test_admin_client_catalog_includes_appliance_tools(self):
        cat = get_tools_catalog(client_id="admin-client", registry=self.mock_registry)
        expected = [
            "gateway_backup",
            "gateway_doctor",
            "gateway_maintenance",
            "gateway_reboot",
            "gateway_status",
        ]
        for t in expected:
            self.assertIn(t, cat)

    def test_readonly_client_invoking_admin_tool_denied(self):
        for tool in ("gateway_status", "gateway_doctor", "gateway_backup", "gateway_maintenance", "gateway_reboot"):
            res = invoke_tool(tool, {"confirm": True}, registry=self.mock_registry, client_id="readonly-client")
            self.assertFalse(res["ok"], f"Expected {tool} to be denied for readonly client")
            self.assertEqual(res["error"]["code"], "TOOL_NOT_ALLOWED")

    def test_gateway_status_success(self):
        tools = GatewayTools(registry=self.mock_registry)
        res = tools.gateway_status()
        self.assertTrue(res["ok"])
        self.assertEqual(res["tool"], "gateway_status")
        result = res["result"]
        self.assertIn("gateway_version", result)
        self.assertIn("memory", result)
        self.assertIn("storage", result)
        self.assertIn("cpu_load", result)

    def test_gateway_doctor_success(self):
        tools = GatewayTools(registry=self.mock_registry)
        res = tools.gateway_doctor()
        self.assertTrue(res["ok"])
        self.assertEqual(res["tool"], "gateway_doctor")
        result = res["result"]
        self.assertIn("status", result)
        self.assertIn("checks", result)
        self.assertGreater(result["checks_count"], 0)

    def test_gateway_reboot_confirmation_required(self):
        tools = GatewayTools(registry=self.mock_registry)
        # Missing or False confirm
        res1 = tools.gateway_reboot(confirm=False)
        self.assertFalse(res1["ok"])
        self.assertEqual(res1["error"]["code"], "INVALID_ARGUMENTS")

        # Explicit True confirm
        res2 = tools.gateway_reboot(confirm=True)
        self.assertTrue(res2["ok"])
        self.assertEqual(res2["tool"], "gateway_reboot")
        self.assertIn("message", res2["result"])


if __name__ == "__main__":
    unittest.main()

"""Unit tests for MCP Gateway Python Core Bridge."""

import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from mcp_gateway.bridge import invoke_tool, main


class TestBridge(unittest.TestCase):

    def setUp(self):
        self.mock_registry = MagicMock()
        self.mock_registry.list_targets.return_value = [{"id": "t1", "enabled": True}]
        self.mock_registry.target_count = 1
        self.mock_registry.get_setting.return_value = "true"

    def test_unallowlisted_tool_rejected(self):
        res = invoke_tool("arbitrary_exec", {}, registry=self.mock_registry)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "TOOL_NOT_ALLOWED")

    def test_health_invocation(self):
        res = invoke_tool("health", {}, registry=self.mock_registry)
        self.assertTrue(res["ok"])
        self.assertEqual(res["tool"], "health")
        self.assertIn("gateway_status", res["result"])

    def test_list_targets_invocation(self):
        res = invoke_tool("list_targets", {}, registry=self.mock_registry)
        self.assertTrue(res["ok"])
        self.assertEqual(res["tool"], "list_targets")
        self.assertIn("targets", res["result"])

    def test_missing_required_argument(self):
        res = invoke_tool("target_status", {}, registry=self.mock_registry)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "INVALID_ARGUMENTS")

        res2 = invoke_tool("read_file", {"target": "t1"}, registry=self.mock_registry)
        self.assertFalse(res2["ok"])
        self.assertEqual(res2["error"]["code"], "INVALID_ARGUMENTS")

    def test_cli_invoke_health(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["invoke", "health"])
        self.assertEqual(code, 0)
        output = json.loads(buf.getvalue())
        self.assertTrue(output["ok"])
        self.assertEqual(output["tool"], "health")

    def test_cli_invalid_json(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["invoke", "target_status", "not_valid_json"])
        self.assertEqual(code, 1)
        output = json.loads(buf.getvalue())
        self.assertFalse(output["ok"])
        self.assertEqual(output["error"]["code"], "INVALID_ARGUMENTS")

    def test_write_file_argument_validation(self):
        res = invoke_tool("write_file", {"target": "t1"}, registry=self.mock_registry)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "INVALID_ARGUMENTS")


if __name__ == "__main__":
    unittest.main()

import unittest
import sqlite3
import tempfile
import os

from mcp_gateway.schema import init_db, get_schema_version, migrate_db

class TestSchema(unittest.TestCase):
    def setUp(self):
        self.fd, self.db_path = tempfile.mkstemp()
        os.close(self.fd)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_init_db(self):
        init_db(self.db_path)
        
        conn = sqlite3.connect(self.db_path)
        
        # Test version
        version = get_schema_version(conn)
        self.assertEqual(version, 1)
        
        # Test tables
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        expected_tables = {
            "targets", "projects", "project_tasks", "ai_clients",
            "grants", "activity", "settings", "admin_users"
        }
        self.assertTrue(expected_tables.issubset(tables))
        
        # Test defaults
        cursor.execute("SELECT key, value FROM settings")
        settings = dict(cursor.fetchall())
        
        self.assertEqual(settings.get("gateway_enabled"), "true")
        self.assertEqual(settings.get("writes_enabled"), "false")
        self.assertEqual(settings.get("default_timeout"), "30")
        self.assertEqual(settings.get("max_output_bytes"), "262144")
        self.assertEqual(settings.get("max_file_read_bytes"), "1048576")
        self.assertEqual(settings.get("max_write_bytes"), "262144")
        self.assertEqual(settings.get("max_diff_bytes"), "65536")
        self.assertEqual(settings.get("activity_retention"), "5000")
        
        conn.close()

import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from mcp_gateway import lifecycle, schema


class TestLifecycle(unittest.TestCase):
    def test_create_and_verify_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            m_path = os.path.join(tmpdir, "manifest.json")
            m = lifecycle.create_manifest(version="0.6.0", output_path=m_path)
            self.assertEqual(m["version"], "0.6.0")
            self.assertTrue(os.path.isfile(m_path))

            ok, errors = lifecycle.verify_manifest(m_path)
            self.assertTrue(ok)
            self.assertEqual(len(errors), 0)

    def test_root_manifest(self):
        root_manifest = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "manifest.json"))
        if os.path.isfile(root_manifest):
            ok, errors = lifecycle.verify_manifest(root_manifest)
            self.assertTrue(ok, f"Root manifest verification failed: {errors}")

    def test_architecture_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            m_path = os.path.join(tmpdir, "manifest.json")
            m = lifecycle.create_manifest(version="0.6.0", output_path=m_path)
            # Tamper with architecture
            m["architecture"] = "non_existent_arch_999"
            m["architectures"] = ["non_existent_arch_999"]
            import json
            with open(m_path, "w", encoding="utf-8") as f:
                json.dump(m, f)

            ok, errors = lifecycle.verify_manifest(m_path)
            self.assertFalse(ok)
            self.assertTrue(any("Architecture mismatch" in err for err in errors))

    def test_backup_and_restore_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            schema.init_db(db_path)

            os.environ["MCP_GATEWAY_DB"] = db_path
            backup_path = os.path.join(tmpdir, "backup.db")

            # Perform backup
            result_path = lifecycle.backup_database(backup_path)
            self.assertEqual(result_path, backup_path)
            self.assertTrue(os.path.isfile(backup_path))

            # Modify db
            conn = sqlite3.connect(db_path)
            conn.execute("INSERT INTO settings (key, value) VALUES ('test_key', 'test_val')")
            conn.commit()
            conn.close()

            # Restore backup
            restored = lifecycle.restore_database(backup_path)
            self.assertTrue(restored)

            # Check that test_key is gone after restore
            conn2 = sqlite3.connect(db_path)
            cur = conn2.cursor()
            cur.execute("SELECT value FROM settings WHERE key = 'test_key'")
            row = cur.fetchone()
            conn2.close()
            self.assertIsNone(row)


if __name__ == "__main__":
    unittest.main()

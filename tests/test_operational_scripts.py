import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestOperationalScripts(unittest.TestCase):
    def test_shell_syntax(self):
        checks = [
            (["sh", "-n", str(ROOT / "install.sh")], ROOT),
            (["bash", "-n", str(ROOT / "scripts" / "deploy-pi.sh")], ROOT),
            (["bash", "-n", str(ROOT / "scripts" / "backup-appliance.sh")], ROOT),
        ]
        for argv, cwd in checks:
            with self.subTest(argv=argv):
                cp = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
                self.assertEqual(cp.returncode, 0, cp.stderr)

    def test_installer_fail_fast_contract(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertNotIn("|| true", text)
        self.assertIn('install.sh must run as root', text)
        self.assertIn('did not become ready within 45 seconds', text)
        self.assertIn('"${INSTALL_DIR}/bin/mcp-gateway" doctor', text)

    def test_deploy_is_exact_commit_and_has_rollback(self):
        text = (ROOT / "scripts" / "deploy-pi.sh").read_text(encoding="utf-8")
        for required in (
            'git -C "${PROJECT_ROOT}" archive',
            'deployment requires a completely clean Git working tree',
            'origin/${DEPLOY_BRANCH}',
            'MCP_DEPLOY_INJECT_FAILURE',
            'ROLLBACK_VERIFIED',
            '.deployment.json',
            "'verified': True",
        ):
            self.assertIn(required, text)
        verified_index = text.index("'verified': True")
        acceptance_index = text.index('[7/10] Running lightweight production acceptance')
        self.assertGreater(verified_index, acceptance_index)

    def test_backup_age_is_optional_and_fail_closed(self):
        text = (ROOT / "scripts" / "backup-appliance.sh").read_text(encoding="utf-8")
        self.assertIn('BACKUP_AGE_RECIPIENT="${BACKUP_AGE_RECIPIENT:-}"', text)
        self.assertIn("optional 'age' binary is not installed", text)
        self.assertIn('refusing plaintext fallback', text)
        self.assertIn('age -r "${BACKUP_AGE_RECIPIENT}"', text)


if __name__ == "__main__":
    unittest.main()

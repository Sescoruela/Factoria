import subprocess
import tempfile
import unittest
from pathlib import Path

from factoria.security import SecretIncident, SecretScanner, SecretSource


class SecretScannerTests(unittest.TestCase):
    def test_redacts_assignment_secret_without_exposing_value(self) -> None:
        value = "synthetic-secret-value-12345"
        text = f'api_key = "{value}"\n'

        sanitized, findings = SecretScanner().redact(text)

        self.assertEqual(len(findings), 1)
        self.assertNotIn(value, sanitized)
        self.assertIn("[REDACTED]", sanitized)
        self.assertEqual(findings[0].preview, "[REDACTED]")
        self.assertNotIn(value, repr(findings[0]))

    def test_file_incident_requires_rotation_confirmation_and_removal(self) -> None:
        scanner = SecretScanner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "config.txt"
            target.write_text('token = "synthetic-secret-value-12345"\n', encoding="utf-8")
            findings = scanner.scan_files(root, ("config.txt",))
            self.assertEqual(findings[0].source, SecretSource.FILE)

            incident = SecretIncident(findings)
            self.assertFalse(scanner.verify_removed(root, incident))
            self.assertFalse(scanner.verify_removed(root, incident.confirm_rotation()))

            target.write_text('token = "removed"\n', encoding="utf-8")
            self.assertTrue(scanner.verify_removed(root, incident.confirm_rotation()))

    def test_changed_paths_reads_git_status_without_leaving_repo(self) -> None:
        scanner = SecretScanner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Factoria Tests"], cwd=root, check=True)
            (root / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, capture_output=True)
            (root / "README.md").write_text("changed\n", encoding="utf-8")

            self.assertEqual(scanner.changed_paths(root), ("README.md",))


if __name__ == "__main__":
    unittest.main()

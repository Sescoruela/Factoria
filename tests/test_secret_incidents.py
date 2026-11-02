from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factoria.security import IncidentStatus, SecretIncidentStore, SecretScanner


class SecretIncidentStoreTests(unittest.TestCase):
    def test_findings_are_persisted_without_raw_secret(self) -> None:
        scanner = SecretScanner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "config.txt"
            fake = "sk-" + "x" * 24
            target.write_text(f"token={fake}\n", encoding="utf-8")
            findings = scanner.scan_files(root, ("config.txt",))
            store = SecretIncidentStore(root)
            created = store.record(findings)
            self.assertEqual(len(created), 1)
            persisted = store.path.read_text(encoding="utf-8")
            self.assertNotIn(fake, persisted)
            self.assertIn(created[0].fingerprint, persisted)
            self.assertEqual(store.open()[0].status, IncidentStatus.OPEN)

    def test_rotation_confirmation_does_not_resolve_while_secret_remains(self) -> None:
        scanner = SecretScanner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = "sk-" + "y" * 24
            (root / "config.txt").write_text(fake, encoding="utf-8")
            store = SecretIncidentStore(root)
            incident = store.record(scanner.scan_files(root, ("config.txt",)))[0]
            with self.assertRaises(RuntimeError):
                store.confirm_rotation_and_resolve(incident.incident_id, scanner)
            current = store.open()[0]
            self.assertIsNotNone(current.rotation_confirmed_at)
            self.assertEqual(current.status, IncidentStatus.OPEN)

    def test_incident_resolves_only_after_confirmation_and_verified_absence(self) -> None:
        scanner = SecretScanner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = "sk-" + "z" * 24
            target = root / "config.txt"
            target.write_text(fake, encoding="utf-8")
            store = SecretIncidentStore(root)
            incident = store.record(scanner.scan_files(root, ("config.txt",)))[0]
            target.write_text("token removed\n", encoding="utf-8")
            resolved = store.confirm_rotation_and_resolve(incident.incident_id, scanner)
            self.assertEqual(resolved.status, IncidentStatus.RESOLVED)
            self.assertIsNotNone(resolved.rotation_confirmed_at)
            self.assertIsNotNone(resolved.resolved_at)
            self.assertEqual(store.open(), ())

    def test_record_deduplicates_same_open_finding(self) -> None:
        scanner = SecretScanner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = "sk-" + "q" * 24
            (root / "config.txt").write_text(fake, encoding="utf-8")
            findings = scanner.scan_files(root, ("config.txt",))
            store = SecretIncidentStore(root)
            first = store.record(findings)
            second = store.record(findings)
            self.assertEqual(len(first), 1)
            self.assertEqual(second, ())
            self.assertEqual(len(store.open()), 1)


if __name__ == "__main__":
    unittest.main()

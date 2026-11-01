from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factoria.application.manual_verification import (
    inspect_manual_verification,
    record_manual_verification,
)
from factoria.domain.models import ProjectMemory


class ManualVerificationTests(unittest.TestCase):
    def _memory(self, steps: tuple[str, ...] = ()) -> ProjectMemory:
        return ProjectMemory(project_name="demo", manual_verification=steps)

    def test_automated_evidence_does_not_require_manual_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "verification.md").write_text(
                "# Verification\n\n- PASS test\n",
                encoding="utf-8",
            )
            requirement = inspect_manual_verification(root, self._memory(("Open app",)))
            self.assertFalse(requirement.required)
            self.assertTrue(requirement.available)

    def test_manual_steps_are_required_when_no_automated_checks_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "verification.md").write_text(
                "# Verification\n\n- No confirmed automated checks selected.\n",
                encoding="utf-8",
            )
            requirement = inspect_manual_verification(
                root,
                self._memory(("Open the affected screen", "Repeat the reported action")),
            )
            self.assertTrue(requirement.required)
            self.assertTrue(requirement.available)
            self.assertEqual(len(requirement.steps), 2)

            path = record_manual_verification(root, requirement)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(payload["confirmed"])
            self.assertEqual(payload["steps"], list(requirement.steps))
            self.assertIn("confirmed_at", payload)

    def test_missing_manual_steps_leave_no_valid_verification_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "verification.md").write_text(
                "# Verification\n\n- No confirmed automated checks selected.\n",
                encoding="utf-8",
            )
            requirement = inspect_manual_verification(root, self._memory())
            self.assertTrue(requirement.required)
            self.assertFalse(requirement.available)
            self.assertIn("No confirmed automated checks", requirement.reason or "")

    def test_missing_verification_artifact_blocks_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            requirement = inspect_manual_verification(Path(temp_dir), self._memory(("Check it",)))
            self.assertTrue(requirement.required)
            self.assertFalse(requirement.available)
            self.assertEqual(requirement.reason, "Verification evidence is missing")


if __name__ == "__main__":
    unittest.main()

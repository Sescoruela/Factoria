from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WindowsPackagingTests(unittest.TestCase):
    def test_launcher_uses_canonical_entrypoint(self) -> None:
        launcher = (ROOT / "packaging" / "windows" / "factoria_launcher.py").read_text(encoding="utf-8")
        self.assertIn("from factoria.entrypoint import main", launcher)
        self.assertIn("raise SystemExit(main())", launcher)

    def test_installer_is_per_user_and_does_not_require_admin(self) -> None:
        installer = (ROOT / "packaging" / "windows" / "Factoria.iss").read_text(encoding="utf-8")
        self.assertIn("DefaultDirName={localappdata}\\Programs\\Factoria", installer)
        self.assertIn("PrivilegesRequired=lowest", installer)
        self.assertIn("ChangesEnvironment=yes", installer)
        self.assertIn('Name: "addtopath"', installer)
        self.assertIn("RemoveFromUserPath", installer)

    def test_windows_workflow_builds_and_smoke_tests_both_executables(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "windows-installer.yml").read_text(encoding="utf-8")
        self.assertIn("pyinstaller", workflow.lower())
        self.assertIn("--copy-metadata factoria", workflow)
        self.assertIn("Smoke test standalone executable", workflow)
        self.assertIn("Smoke test installer", workflow)
        self.assertRegex(workflow, re.compile(r"Factoria-Setup-.*\.exe"))


if __name__ == "__main__":
    unittest.main()

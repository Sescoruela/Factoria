from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factoria.ui_app import ManagedTerminalUI
from factoria.ui_workspace import UiWorkspaceSettings, discover_projects


class UiWorkspaceTests(unittest.TestCase):
    def test_workspace_settings_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            path = base / "ui.json"
            root = base / "projects"
            project = root / "demo"
            root.mkdir()
            project.mkdir()
            settings = UiWorkspaceSettings(projects_root=root, last_project=project)
            settings.save(path)

            loaded = UiWorkspaceSettings.load(path)
            self.assertEqual(loaded.projects_root, root)
            self.assertEqual(loaded.last_project, project)

    def test_discover_projects_only_returns_git_repositories(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "alpha"
            other = root / "notes"
            project.mkdir()
            other.mkdir()
            (project / ".git").mkdir()

            self.assertEqual(discover_projects(root), (project.resolve(),))


class ManagedTerminalUiTests(unittest.TestCase):
    def test_first_run_continues_to_dashboard_after_onboarding(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output: list[str] = []
            answers = iter(["", "0"])
            ui = ManagedTerminalUI(
                root,
                input_fn=lambda _prompt: next(answers),
                output_fn=output.append,
                command_runner=lambda _args: 0,
            )
            calls: list[str] = []
            ui._onboarding_complete = lambda: False  # type: ignore[method-assign]
            ui.run_onboarding = lambda: calls.append("onboarding") or 0  # type: ignore[method-assign]
            ui._ensure_project_context = lambda: calls.append("context")  # type: ignore[method-assign]
            ui._render_dashboard = lambda: calls.append("dashboard")  # type: ignore[method-assign]

            self.assertEqual(ui.run(), 0)
            self.assertEqual(calls, ["onboarding", "context", "dashboard"])

    def test_dashboard_degrades_cleanly_when_git_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output: list[str] = []
            ui = ManagedTerminalUI(root, output_fn=output.append, command_runner=lambda _args: 0)
            ui.workspace_settings = UiWorkspaceSettings(projects_root=root, last_project=None)

            with patch("factoria.ui_app.shutil.which", return_value=None):
                ui._render_dashboard()

            rendered = "\n".join(output)
            self.assertIn("Git      : NO DISPONIBLE", rendered)
            self.assertNotIn("No se pudo cargar el dashboard", rendered)


if __name__ == "__main__":
    unittest.main()

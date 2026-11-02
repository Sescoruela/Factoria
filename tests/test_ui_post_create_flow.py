from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factoria.ui_project_flow import ProjectFlowTerminalUI
from factoria.ui_workspace import UiWorkspaceSettings


class ProjectPostCreateFlowTests(unittest.TestCase):
    def test_manage_projects_returns_to_dashboard_after_successful_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            answers = iter(["2"])
            ui = ProjectFlowTerminalUI(
                root,
                input_fn=lambda _prompt: next(answers),
                output_fn=lambda _line: None,
                command_runner=lambda _args: 0,
            )
            ui.workspace_settings = UiWorkspaceSettings(projects_root=root, last_project=None)
            calls: list[str] = []
            ui._create_project_and_prepare = lambda: calls.append("create") or True  # type: ignore[method-assign]

            ui._manage_projects()

            self.assertEqual(calls, ["create"])

    def test_create_project_without_memory_returns_ready_for_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects_root = Path(temp)
            output: list[str] = []
            answers = iter([
                "Organizador",
                "Organiza turnos por medias horas",
                "s",
                "n",
                "n",
            ])
            ui = ProjectFlowTerminalUI(
                projects_root,
                input_fn=lambda _prompt: next(answers),
                output_fn=output.append,
                command_runner=lambda _args: 0,
            )
            ui.workspace_settings = UiWorkspaceSettings(projects_root=projects_root, last_project=None)

            completed = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")
            with patch("factoria.ui_project_flow.shutil.which", return_value="git"), patch(
                "factoria.ui_project_flow.subprocess.run", return_value=completed
            ), patch("factoria.ui_project_flow.UiWorkspaceSettings.save", autospec=True):
                created = ui._create_project_and_prepare()

            self.assertTrue(created)
            self.assertEqual(ui.root, (projects_root / "organizador").resolve())
            rendered = "\n".join(output)
            self.assertIn("Memoria Factoria pendiente", rendered)
            self.assertIn("Volviendo al dashboard del proyecto", rendered)

    def test_create_project_can_prepare_memory_before_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects_root = Path(temp)
            output: list[str] = []
            commands: list[list[str]] = []
            answers = iter([
                "Organizador",
                "Organiza turnos por medias horas",
                "s",
                "n",
                "s",
            ])
            ui = ProjectFlowTerminalUI(
                projects_root,
                input_fn=lambda _prompt: next(answers),
                output_fn=output.append,
                command_runner=lambda args: commands.append(list(args)) or 0,
            )
            ui.workspace_settings = UiWorkspaceSettings(projects_root=projects_root, last_project=None)

            completed = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")
            with patch("factoria.ui_project_flow.shutil.which", return_value="git"), patch(
                "factoria.ui_project_flow.subprocess.run", return_value=completed
            ), patch("factoria.ui_project_flow.UiWorkspaceSettings.save", autospec=True):
                created = ui._create_project_and_prepare()

            self.assertTrue(created)
            self.assertEqual(
                commands,
                [[
                    "memoria-init",
                    "--name",
                    "Organizador",
                    "--yes",
                    "--purpose",
                    "Organiza turnos por medias horas",
                ]],
            )
            rendered = "\n".join(output)
            self.assertIn("Memoria Factoria preparada", rendered)
            self.assertIn("Volviendo al dashboard del proyecto", rendered)


if __name__ == "__main__":
    unittest.main()

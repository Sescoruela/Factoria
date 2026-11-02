from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from factoria.ui_agent_tools import AgentAwareTerminalUI


class AgentToolUiTests(unittest.TestCase):
    def test_dashboard_shows_codex_and_opencode_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output: list[str] = []
            ui = AgentAwareTerminalUI(root, output_fn=output.append, command_runner=lambda _args: 0)
            statuses = (
                SimpleNamespace(name="codex", passed=True, available=True, checks=()),
                SimpleNamespace(name="opencode", passed=False, available=False, checks=()),
            )
            with patch.object(AgentAwareTerminalUI.__mro__[1], "_render_dashboard", return_value=None), patch(
                "factoria.ui_agent_tools.SetupService.inspect_tools", return_value=statuses
            ):
                ui._render_dashboard()

            rendered = "\n".join(output)
            self.assertIn("codex   : LISTO", rendered)
            self.assertIn("opencode: NO DETECTADO", rendered)
            self.assertIn("Autenticación", rendered)

    def test_configure_ready_agent_uses_existing_install_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            commands: list[list[str]] = []
            answers = iter(["1", "s"])
            ui = AgentAwareTerminalUI(
                root,
                input_fn=lambda _prompt: next(answers),
                output_fn=lambda _line: None,
                command_runner=lambda args: commands.append(list(args)) or 0,
            )
            statuses = (
                SimpleNamespace(name="codex", passed=True, available=True, checks=()),
                SimpleNamespace(name="opencode", passed=False, available=False, checks=()),
            )
            with patch("factoria.ui_agent_tools.SetupService.inspect_tools", return_value=statuses):
                ui._configure_agents()

            self.assertEqual(commands, [["install", "--default-tool", "codex", "--yes"]])

    def test_explicit_executable_directory_is_added_to_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable = root / "codex.exe"
            executable.write_text("fixture", encoding="utf-8")
            answers = iter(["codex", str(executable)])
            ui = AgentAwareTerminalUI(
                root,
                input_fn=lambda _prompt: next(answers),
                output_fn=lambda _line: None,
                command_runner=lambda _args: 0,
            )
            status = SimpleNamespace(name="codex", passed=True, available=True, checks=())
            original_path = os.environ.get("PATH", "")
            try:
                with patch("factoria.ui_agent_tools._save_agent_paths"), patch(
                    "factoria.ui_agent_tools.SetupService.inspect_tools", return_value=(status,)
                ):
                    ui._configure_agent_path()
                self.assertEqual(ui.agent_paths["codex"], str(executable.resolve()))
                self.assertEqual(os.environ["PATH"].split(os.pathsep)[0], str(root.resolve()))
            finally:
                os.environ["PATH"] = original_path


if __name__ == "__main__":
    unittest.main()

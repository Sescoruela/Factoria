from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from factoria.ui_cli import TerminalUI, _slug, build_parser


class TerminalUiTests(unittest.TestCase):
    def _repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Factoria Test"], check=True)
        (root / "README.md").write_text("# fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-m", "fixture"], check=True, capture_output=True)

    def test_parser_exposes_ui_and_onboarding(self) -> None:
        parser = build_parser()
        self.assertEqual(parser.parse_args(["ui"]).command, "ui")
        self.assertEqual(parser.parse_args(["onboarding"]).command, "onboarding")

    def test_onboarding_state_is_local_to_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._repo(root)
            answers = iter(["", "", "n", ""])
            output: list[str] = []
            ui = TerminalUI(
                root,
                read_only=True,
                input_fn=lambda _prompt: next(answers),
                output_fn=output.append,
                command_runner=lambda _args: self.fail("read-only onboarding should not execute commands"),
            )

            self.assertEqual(ui.run_onboarding(), 0)
            state_path = root / ".git" / "factoria" / "ui-state.json"
            self.assertTrue(state_path.exists())
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertTrue(state["onboarding_completed"])
            self.assertFalse((root / ".factoria" / "ui-state.json").exists())
            self.assertTrue(ui._onboarding_complete())

    def test_feature_action_dispatches_safe_cli_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._repo(root)
            answers = iter(["Añadir panel de estado", "", "1", ""])
            commands: list[list[str]] = []
            ui = TerminalUI(
                root,
                input_fn=lambda _prompt: next(answers),
                output_fn=lambda _text: None,
                command_runner=lambda args: commands.append(list(args)) or 0,
            )

            ui._start_flow("feature")

            self.assertEqual(
                commands,
                [[
                    "feature",
                    "Añadir panel de estado",
                    "--branch",
                    "feature/anadir-panel-de-estado",
                    "--tool",
                    "opencode",
                ]],
            )

    def test_slug_is_portable_and_bounded(self) -> None:
        self.assertEqual(_slug("Añadir UI / Onboarding"), "anadir-ui-onboarding")
        self.assertLessEqual(len(_slug("x" * 100)), 48)


if __name__ == "__main__":
    unittest.main()

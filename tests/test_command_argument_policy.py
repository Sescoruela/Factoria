from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from factoria.adapters import (
    AgentRequest,
    ArgumentPolicyError,
    CodexAdapter,
    OpenCodeAdapter,
    validate_adapter_args,
)


class CommandArgumentPolicyTests(unittest.TestCase):
    @patch.object(CodexAdapter, "_resolved_executable", return_value=None)
    def test_codex_accepts_only_expected_read_only_safety_flags(self, _discovery) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            command = CodexAdapter().build_command(
                AgentRequest(
                    prompt="Inspect",
                    project_root=Path(tmp),
                    extra_args=("--sandbox", "read-only", "--ask-for-approval", "never"),
                )
            )
        self.assertEqual(
            command[:6],
            ("codex", "--sandbox", "read-only", "--ask-for-approval", "never", "exec"),
        )

    def test_codex_rejects_model_override_through_extra_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request = AgentRequest(
                prompt="Inspect",
                project_root=Path(tmp),
                model="approved-model",
                extra_args=("--model", "unapproved-model"),
            )
            with self.assertRaises(ArgumentPolicyError):
                CodexAdapter().build_command(request)

    def test_codex_rejects_sandbox_escalation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request = AgentRequest(
                prompt="Inspect",
                project_root=Path(tmp),
                extra_args=("--sandbox", "workspace-write"),
            )
            with self.assertRaises(ArgumentPolicyError):
                CodexAdapter().build_command(request)

    def test_opencode_rejects_all_extra_cli_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request = AgentRequest(
                prompt="Inspect",
                project_root=Path(tmp),
                extra_args=("--dir", "/tmp/escape"),
            )
            with self.assertRaises(ArgumentPolicyError):
                OpenCodeAdapter().build_command(request)

    def test_external_adapter_without_policy_never_receives_extra_args(self) -> None:
        class ExternalAdapter:
            pass

        with self.assertRaises(ArgumentPolicyError):
            validate_adapter_args(ExternalAdapter(), ("--unsafe",))

    def test_external_adapter_without_policy_is_compatible_when_no_args_are_needed(self) -> None:
        class ExternalAdapter:
            pass

        self.assertEqual(validate_adapter_args(ExternalAdapter(), ()), ())


if __name__ == "__main__":
    unittest.main()

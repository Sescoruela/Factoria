from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factoria.adapters import (
    AdapterRegistry,
    AdapterSelectionError,
    AgentRequest,
    CodexAdapter,
    OpenCodeAdapter,
    ToolCapability,
)


class AdapterCommandTests(unittest.TestCase):
    @patch.object(CodexAdapter, "_resolved_executable", return_value=None)
    def test_codex_builds_non_interactive_command(self, _discovery) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request = AgentRequest(
                prompt="Review this repository",
                project_root=Path(tmp),
                model="gpt-test",
                structured_output=True,
            )
            command = CodexAdapter().build_command(request)

        self.assertEqual(command[:3], ("codex", "exec", "--json"))
        self.assertIn("--model", command)
        self.assertEqual(command[-1], "Review this repository")

    def test_opencode_builds_run_command_with_project_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = AgentRequest(
                prompt="Explain this repository",
                project_root=root,
                model="provider/model",
                structured_output=True,
            )
            command = OpenCodeAdapter().build_command(request)

        self.assertEqual(command[:2], ("opencode", "run"))
        self.assertIn("--dir", command)
        self.assertIn(str(root), command)
        self.assertIn("--format", command)
        self.assertEqual(command[-1], "Explain this repository")

    def test_empty_prompt_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AgentRequest(prompt=" ", project_root=Path("."))


class AdapterRegistryTests(unittest.TestCase):
    def test_preferred_adapter_is_selected_when_available(self) -> None:
        codex = CodexAdapter()
        opencode = OpenCodeAdapter()
        registry = AdapterRegistry({"codex": codex, "opencode": opencode})

        with patch.object(CodexAdapter, "available", return_value=True), patch.object(
            OpenCodeAdapter, "available", return_value=True
        ):
            selected = registry.select(
                preferred="codex",
                required_capabilities=frozenset({ToolCapability.NON_INTERACTIVE}),
            )

        self.assertEqual(selected.name, "codex")

    def test_registry_falls_back_to_compatible_adapter(self) -> None:
        codex = CodexAdapter()
        opencode = OpenCodeAdapter()
        registry = AdapterRegistry({"codex": codex, "opencode": opencode})

        with patch.object(CodexAdapter, "available", return_value=False), patch.object(
            OpenCodeAdapter, "available", return_value=True
        ):
            selected = registry.select(
                preferred="codex",
                required_capabilities=frozenset({ToolCapability.STRUCTURED_OUTPUT}),
            )

        self.assertEqual(selected.name, "opencode")

    def test_registry_fails_if_no_adapter_is_available(self) -> None:
        registry = AdapterRegistry({"codex": CodexAdapter()})
        with patch.object(CodexAdapter, "available", return_value=False):
            with self.assertRaises(AdapterSelectionError):
                registry.select(preferred="codex")


if __name__ == "__main__":
    unittest.main()

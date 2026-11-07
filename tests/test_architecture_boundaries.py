"""Layering contracts explicitly required by AGENTS.md."""

import ast
from importlib.resources import files
from pathlib import Path
import unittest


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_domain_config_and_memory_do_not_depend_on_application_or_adapters(self):
        root = Path(str(files("factoria")))
        violations = []
        for layer in ("domain", "config", "memory"):
            for path in (root / layer).glob("*.py"):
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                    imported = (
                        [node.module or ""]
                        if isinstance(node, ast.ImportFrom)
                        else [a.name for a in node.names]
                        if isinstance(node, ast.Import)
                        else []
                    )
                    if any(
                        name.startswith(("factoria.application", "factoria.adapters"))
                        for name in imported
                    ):
                        violations.append(str(path.relative_to(root)))
        self.assertEqual(violations, [])

    def test_old_memory_change_import_remains_the_same_domain_contract(self):
        from factoria.application.memory_flows import MemoryChange as old
        from factoria.domain.models import MemoryChange

        self.assertIs(old, MemoryChange)
        self.assertEqual(old("metadata", "review").evidence, ())

    def test_old_project_path_import_remains_the_same_safety_contract(self):
        from factoria.application.project_integration import project_path as old
        from factoria.project_paths import project_path

        self.assertIs(old, project_path)

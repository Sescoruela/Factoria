"""Layering contracts explicitly required by AGENTS.md."""

import ast
from importlib.resources import files
from pathlib import Path
import unittest


class ArchitectureBoundaryTests(unittest.TestCase):
    def assert_no_imports(self, layers, forbidden):
        root = Path(str(files("factoria")))
        violations = []
        for layer in layers:
            for path in (root / layer).rglob("*.py"):
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                    imported = (
                        [node.module or ""]
                        if isinstance(node, ast.ImportFrom)
                        else [a.name for a in node.names]
                        if isinstance(node, ast.Import)
                        else []
                    )
                    for name in imported:
                        if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden):
                            violations.append((str(path.relative_to(root)), name))
        self.assertEqual(violations, [])

    def test_domain_config_and_memory_do_not_depend_on_application_or_adapters(self):
        self.assert_no_imports(
            ("domain", "config", "memory"),
            ("factoria.application", "factoria.adapters"),
        )

    def test_application_services_do_not_import_interfaces(self):
        self.assert_no_imports(
            ("application",),
            ("factoria.commands", "factoria.ui", "factoria.web", "factoria.cli", "factoria.entrypoint"),
        )

    def test_old_memory_change_import_remains_the_same_domain_contract(self):
        from factoria.application.memory_flows import MemoryChange as old
        from factoria.domain.models import MemoryChange

        self.assertIs(old, MemoryChange)
        self.assertEqual(old("metadata", "review").evidence, ())

    def test_old_project_path_import_remains_the_same_safety_contract(self):
        from factoria.application.project_integration import project_path as old
        from factoria.project_paths import project_path

        self.assertIs(old, project_path)

    def test_legacy_interfaces_resolve_to_the_canonical_implementations(self):
        from factoria.commands.project import run_project_cli
        from factoria.project_cli import run_project_cli as old_project_cli
        from factoria.web.backend.main_shell import FactoriaN8NHandler
        from factoria.web.backend.server import FactoriaWebHandler
        from factoria.web_app import FactoriaWebHandler as old_web_handler
        from factoria.web_app_n8n import FactoriaN8NHandler as old_main_handler

        self.assertIs(old_project_cli, run_project_cli)
        self.assertIs(old_main_handler, FactoriaN8NHandler)
        self.assertIs(old_web_handler, FactoriaWebHandler)

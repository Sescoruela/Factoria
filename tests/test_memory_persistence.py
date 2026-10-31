from __future__ import annotations

import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import MappingProxyType

from factoria.domain.models import (
    ConfirmedCommand,
    MemoryDocumentKind,
    MemoryMetadata,
    ModuleMemory,
    ProjectKind,
    ProjectMemory,
)
from factoria.memory.git_staleness import GitMemoryStalenessInspector
from factoria.memory.loader import MemoryFormatError, load_project_memory
from factoria.memory.renderer import render_agents_md, render_memory_document


class MemoryPersistenceTests(unittest.TestCase):
    def test_round_trip_preserves_confirmed_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs" / "memoria"
            docs.mkdir(parents=True)
            memory = ProjectMemory(
                project_name="demo",
                purpose="Proyecto de prueba",
                metadata=MemoryMetadata(
                    reviewed_commit="abc123",
                    reviewed_at=date(2026, 10, 31),
                    factoria_version="0.1.0",
                    project_kind=ProjectKind.ACTIVE,
                ),
                technologies=("python",),
                modules=(ModuleMemory(name="api", paths=("api/",), affects=("web",)),),
                dependencies=MappingProxyType({"api": ("web",)}),
                confirmed_check_commands=(
                    ConfirmedCommand(
                        category="test",
                        command=("python", "-m", "unittest", "tests.test demo"),
                        scope="api",
                        required=True,
                        global_check=False,
                    ),
                ),
                mandatory_rules=("No borrar datos",),
                decisions=("Usar stdlib",),
                manual_verification=("Abrir /health",),
            )
            (root / "AGENTS.md").write_text(render_agents_md(memory), encoding="utf-8")
            for kind, name in (
                (MemoryDocumentKind.ARCHITECTURE, "arquitectura.md"),
                (MemoryDocumentKind.FLOWS, "flujos.md"),
                (MemoryDocumentKind.DECISIONS, "decisiones.md"),
                (MemoryDocumentKind.TESTING, "testing.md"),
            ):
                (docs / name).write_text(render_memory_document(memory, kind), encoding="utf-8")

            loaded = load_project_memory(root)

            self.assertEqual(loaded.project_name, memory.project_name)
            self.assertEqual(loaded.purpose, memory.purpose)
            self.assertEqual(loaded.technologies, memory.technologies)
            self.assertEqual(loaded.modules, memory.modules)
            self.assertEqual(dict(loaded.dependencies), dict(memory.dependencies))
            self.assertEqual(loaded.confirmed_check_commands, memory.confirmed_check_commands)
            self.assertEqual(loaded.mandatory_rules, memory.mandatory_rules)
            self.assertEqual(loaded.decisions, memory.decisions)
            self.assertEqual(loaded.manual_verification, memory.manual_verification)

    def test_invalid_header_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# handwritten\n", encoding="utf-8")
            with self.assertRaises(MemoryFormatError):
                load_project_memory(root)

    def test_git_staleness_uses_commits_since_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init")
            self._git(root, "config", "user.email", "tests@example.com")
            self._git(root, "config", "user.name", "Tests")
            (root / "one.txt").write_text("one", encoding="utf-8")
            self._git(root, "add", "one.txt")
            self._git(root, "commit", "-m", "one")
            reviewed = self._git(root, "rev-parse", "HEAD").strip()
            (root / "two.txt").write_text("two", encoding="utf-8")
            self._git(root, "add", "two.txt")
            self._git(root, "commit", "-m", "two")

            memory = ProjectMemory(
                project_name="demo",
                metadata=MemoryMetadata(
                    reviewed_commit=reviewed,
                    reviewed_at=date(2026, 10, 31),
                    factoria_version="0.1.0",
                    project_kind=ProjectKind.ACTIVE,
                ),
            )
            report = GitMemoryStalenessInspector().inspect(
                root,
                memory,
                threshold_overrides=MappingProxyType(
                    {MemoryDocumentKind.ARCHITECTURE: 1}
                ),
            )

            self.assertEqual(report.commits_since_review, 1)
            self.assertIn(MemoryDocumentKind.ARCHITECTURE, report.stale_documents)

    @staticmethod
    def _git(root: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return completed.stdout


if __name__ == "__main__":
    unittest.main()

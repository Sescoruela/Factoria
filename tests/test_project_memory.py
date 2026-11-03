from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from factoria.domain.models import (
    MemoryDocumentKind,
    MemoryMetadata,
    ModuleMemory,
    ProjectKind,
    ProjectMemory,
)
from factoria.memory.filesystem import memory_targets, write_initial_memory
from factoria.memory.initializer import GitActivitySnapshot, MemoryInitializer
from factoria.memory.renderer import render_agents_md
from factoria.memory.staleness import MemoryStalenessPolicy


class StaticTechnologyDetector:
    def detect(self, project_root: Path) -> tuple[str, ...]:
        return ("dotnet", "angular", "dotnet")


class StaticModuleDetector:
    def detect(self, project_root: Path) -> tuple[ModuleMemory, ...]:
        return (
            ModuleMemory(name="backend", paths=("backend/",)),
            ModuleMemory(name="frontend", paths=("frontend/",)),
        )


class StaticActivityAnalyzer:
    def analyze(self, project_root: Path) -> GitActivitySnapshot:
        return GitActivitySnapshot(
            commits_last_30_days=12,
            active_branches=2,
            suggested_kind=ProjectKind.ACTIVE,
        )


class ProjectMemoryTests(unittest.TestCase):
    def _memory(self, kind: ProjectKind = ProjectKind.ACTIVE) -> ProjectMemory:
        return ProjectMemory(
            project_name="Demo",
            purpose="Proyecto de ejemplo",
            metadata=MemoryMetadata(
                reviewed_commit="abc123",
                reviewed_at=date(2026, 10, 30),
                factoria_version="0.1.0",
                project_kind=kind,
            ),
            technologies=("dotnet", "angular"),
            modules=(ModuleMemory(name="backend", paths=("backend/",)),),
            mandatory_rules=("No cambiar contratos públicos sin aprobación.",),
            manual_verification=("Arrancar la aplicación y completar el flujo principal.",),
        )

    def test_agents_md_is_short_index_with_metadata(self) -> None:
        rendered = render_agents_md(self._memory())
        self.assertIn("reviewed_commit=abc123", rendered)
        self.assertIn("docs/memoria/arquitectura.md", rendered)
        self.assertIn("No cambiar contratos públicos", rendered)

    def test_maintenance_memory_does_not_create_deep_architecture_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            memory = self._memory(ProjectKind.MAINTENANCE)
            written = write_initial_memory(root, memory)
            relative = {item.path.relative_to(root).as_posix() for item in written}

            self.assertEqual(relative, {"AGENTS.md", "docs/memoria/testing.md"})

    def test_initial_writer_refuses_to_overwrite_existing_agents_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            (root / "AGENTS.md").write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_initial_memory(root, self._memory())

    def test_staleness_thresholds_are_per_document(self) -> None:
        policy = MemoryStalenessPolicy()
        self.assertTrue(policy.is_stale(MemoryDocumentKind.FLOWS, 15))
        self.assertFalse(policy.is_stale(MemoryDocumentKind.ARCHITECTURE, 24))
        self.assertTrue(policy.is_stale(MemoryDocumentKind.ARCHITECTURE, 25))

    def test_memoria_init_requires_confirmation_before_writing(self) -> None:
        initializer = MemoryInitializer(
            technology_detector=StaticTechnologyDetector(),
            module_detector=StaticModuleDetector(),
            activity_analyzer=StaticActivityAnalyzer(),
            factoria_version="0.1.0",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            proposal = initializer.propose(
                Path(temp_dir),
                project_name="Demo",
                reviewed_commit="abc123",
                today=date(2026, 10, 30),
            )

            self.assertEqual(proposal.memory.technologies, ("dotnet", "angular"))
            self.assertEqual(proposal.memory.metadata.project_kind, ProjectKind.ACTIVE)
            with self.assertRaises(PermissionError):
                initializer.require_confirmation(proposal)

            confirmed = initializer.require_confirmation(proposal.confirm())
            self.assertEqual(confirmed.project_name, "Demo")

    def test_active_project_targets_include_full_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            targets = {path.relative_to(root).as_posix() for path in memory_targets(root, self._memory())}
            self.assertIn("docs/memoria/arquitectura.md", targets)
            self.assertIn("docs/memoria/flujos.md", targets)
            self.assertIn("docs/memoria/decisiones.md", targets)


if __name__ == "__main__":
    unittest.main()

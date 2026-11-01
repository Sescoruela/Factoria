from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from factoria.application.memory_bootstrap import (
    MemoryBootstrapService,
    RepositoryBootstrapAnalyzer,
)
from factoria.domain.models import MemoryMetadata, ModuleMemory, ProjectKind, ProjectMemory
from factoria.memory.filesystem import write_initial_memory
from factoria.memory.initializer import GitActivitySnapshot, MemoryInitializer
from factoria.memory.loader import load_project_memory


class StaticTechnologyDetector:
    def detect(self, project_root: Path) -> tuple[str, ...]:
        return ("javascript-typescript",)


class StaticModuleDetector:
    def detect(self, project_root: Path) -> tuple[ModuleMemory, ...]:
        return (
            ModuleMemory(name="frontend", paths=("frontend/",)),
            ModuleMemory(name="shared", paths=("shared/",)),
        )


class StaticActivityAnalyzer:
    def analyze(self, project_root: Path) -> GitActivitySnapshot:
        return GitActivitySnapshot(
            commits_last_30_days=8,
            active_branches=2,
            suggested_kind=ProjectKind.ACTIVE,
        )


class MemoryBootstrapTests(unittest.TestCase):
    def _initializer(self) -> MemoryInitializer:
        return MemoryInitializer(
            technology_detector=StaticTechnologyDetector(),
            module_detector=StaticModuleDetector(),
            activity_analyzer=StaticActivityAnalyzer(),
            factoria_version="0.2.0",
        )

    def test_package_scripts_and_module_dependency_are_proposed_from_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            frontend = root / "frontend"
            shared = root / "shared"
            frontend.mkdir()
            shared.mkdir()
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            (frontend / "package.json").write_text(
                json.dumps(
                    {
                        "name": "@demo/frontend",
                        "scripts": {"test": "vitest", "lint": "eslint ."},
                        "dependencies": {"@demo/shared": "workspace:*"},
                    }
                ),
                encoding="utf-8",
            )
            (shared / "package.json").write_text(
                json.dumps({"name": "@demo/shared", "scripts": {"build": "tsc"}}),
                encoding="utf-8",
            )

            base = ProjectMemory(
                project_name="Demo",
                metadata=MemoryMetadata(
                    reviewed_commit="abc",
                    reviewed_at=date(2026, 11, 1),
                    factoria_version="0.2.0",
                    project_kind=ProjectKind.ACTIVE,
                ),
                technologies=("javascript-typescript",),
                modules=StaticModuleDetector().detect(root),
            )
            enriched, evidence = RepositoryBootstrapAnalyzer().enrich(root, base)

            commands = {(item.category, item.scope, item.command) for item in enriched.confirmed_check_commands}
            self.assertIn(("test", "frontend", ("npm", "run", "test")), commands)
            self.assertIn(("lint", "frontend", ("npm", "run", "lint")), commands)
            self.assertIn(("build", "shared", ("npm", "run", "build")), commands)
            self.assertEqual(enriched.dependencies["frontend"], ("shared",))
            self.assertTrue(any(item.target == "dependency:frontend->shared" for item in evidence))

    def test_proposal_includes_project_config_and_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "frontend").mkdir()
            (root / "shared").mkdir()
            service = MemoryBootstrapService(self._initializer())
            proposal = service.propose(
                root,
                project_name="Demo",
                reviewed_commit="abc123",
                purpose="Example",
            )

            self.assertTrue(proposal.write_config)
            self.assertIn('[memory]', proposal.config_text)
            self.assertIn('type = "active"', proposal.config_text)
            self.assertIn("architecture = 25", proposal.config_text)
            self.assertIn("maintainability", proposal.memory.non_functional_priorities)
            with self.assertRaises(PermissionError):
                service.apply(root, proposal)

            written = service.apply(root, proposal.confirm())
            relative = {path.relative_to(root).as_posix() for path in written}
            self.assertIn(".factoria/config.toml", relative)
            self.assertIn("AGENTS.md", relative)

    def test_existing_project_config_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "frontend").mkdir()
            (root / "shared").mkdir()
            config = root / ".factoria" / "config.toml"
            config.parent.mkdir()
            config.write_text('profile = "safe"\n', encoding="utf-8")
            service = MemoryBootstrapService(self._initializer())
            proposal = service.propose(root, project_name="Demo", reviewed_commit="abc")
            self.assertFalse(proposal.write_config)
            service.apply(root, proposal.confirm())
            self.assertEqual(config.read_text(encoding="utf-8"), 'profile = "safe"\n')

    def test_non_functional_priorities_round_trip_through_memory_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            memory = ProjectMemory(
                project_name="Demo",
                metadata=MemoryMetadata(
                    reviewed_commit="abc",
                    reviewed_at=date(2026, 11, 1),
                    factoria_version="0.2.0",
                    project_kind=ProjectKind.ACTIVE,
                ),
                non_functional_priorities=("security", "maintainability"),
            )
            write_initial_memory(root, memory)
            loaded = load_project_memory(root)
            self.assertEqual(loaded.non_functional_priorities, ("security", "maintainability"))

    def test_kind_override_changes_memory_and_generated_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "frontend").mkdir()
            (root / "shared").mkdir()
            proposal = MemoryBootstrapService(self._initializer()).propose(
                root,
                project_name="Demo",
                reviewed_commit="abc",
                project_kind=ProjectKind.MAINTENANCE,
            )
            self.assertEqual(proposal.memory.metadata.project_kind, ProjectKind.MAINTENANCE)
            self.assertIn('type = "maintenance"', proposal.config_text)
            self.assertNotIn("reliability", proposal.memory.non_functional_priorities)


if __name__ == "__main__":
    unittest.main()

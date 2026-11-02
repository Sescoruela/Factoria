from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factoria.application.impact import ImpactAnalyzer
from factoria.domain.models import (
    ContractMemory,
    ExternalDependency,
    ModuleMemory,
    ProjectMemory,
)
from factoria.memory.renderer import render_agents_md
from factoria.memory.loader import load_project_memory
from factoria.domain.models import MemoryMetadata, ProjectKind
from datetime import date


class ImpactAnalyzerTests(unittest.TestCase):
    def test_contract_change_blocks_when_external_consumer_is_declared(self) -> None:
        memory = ProjectMemory(
            project_name="demo",
            modules=(
                ModuleMemory("backend", ("backend",), ("frontend",)),
                ModuleMemory("frontend", ("frontend",)),
            ),
            external_dependencies=(
                ExternalDependency("mobile-app", "org/mobile", "consumes REST API"),
            ),
            contracts=(
                ContractMemory(
                    "public-api",
                    ("backend/openapi.yaml",),
                    affects_modules=("frontend",),
                    affects_external=("mobile-app",),
                ),
            ),
        )
        report = ImpactAnalyzer().analyze(memory, ("backend/openapi.yaml",))
        self.assertTrue(report.blocking)
        self.assertEqual(tuple(item.name for item in report.contract_impacts), ("public-api",))
        self.assertEqual(tuple(item.name for item in report.external_impacts), ("mobile-app",))

    def test_internal_transitive_impact_is_inferred_but_not_external_blocking(self) -> None:
        memory = ProjectMemory(
            project_name="demo",
            modules=(
                ModuleMemory("core", ("src/core",), ("api",)),
                ModuleMemory("api", ("src/api",), ("ui",)),
                ModuleMemory("ui", ("src/ui",)),
            ),
        )
        report = ImpactAnalyzer().analyze(memory, ("src/core/service.py",))
        self.assertFalse(report.blocking)
        inferred = {(item.name, item.confidence) for item in report.items}
        self.assertIn(("api", "inferred"), inferred)
        self.assertIn(("ui", "inferred"), inferred)

    def test_contract_memory_round_trips_through_agents_md(self) -> None:
        memory = ProjectMemory(
            project_name="demo",
            metadata=MemoryMetadata(
                reviewed_commit="abc123",
                reviewed_at=date(2026, 11, 2),
                factoria_version="0.2.0",
                project_kind=ProjectKind.ACTIVE,
            ),
            external_dependencies=(
                ExternalDependency("mobile", "org/mobile", "consumes schema"),
            ),
            contracts=(
                ContractMemory("schema", ("api/schema.json",), affects_external=("mobile",)),
            ),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text(render_agents_md(memory), encoding="utf-8")
            loaded = load_project_memory(root)
        self.assertEqual(loaded.external_dependencies, memory.external_dependencies)
        self.assertEqual(loaded.contracts, memory.contracts)


if __name__ == "__main__":
    unittest.main()

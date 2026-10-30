from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from factoria.application.memory_flows import MemoryChange, MemoryUpdateFlow
from factoria.domain.models import MemoryMetadata, ProjectKind, ProjectMemory


class Analyzer:
    def analyze(self, project_root: Path, current: ProjectMemory) -> ProjectMemory:
        return replace(current, decisions=(*current.decisions, "Keep core tool-agnostic"))


class MemoryUpdateFlowTests(unittest.TestCase):
    def test_update_requires_confirmation_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            current = ProjectMemory(
                project_name="Demo",
                metadata=MemoryMetadata(
                    reviewed_commit="abc",
                    reviewed_at=date(2026, 10, 1),
                    factoria_version="0.1.0",
                    project_kind=ProjectKind.ACTIVE,
                ),
            )
            flow = MemoryUpdateFlow(analyzer=Analyzer(), factoria_version="0.1.0")
            proposal = flow.propose(
                project_root,
                current,
                reviewed_commit="def",
                changes=(
                    MemoryChange(
                        target="docs/memoria/decisiones.md",
                        reason="New architecture decision",
                        evidence=("src/factoria/application/",),
                    ),
                ),
                today=date(2026, 10, 30),
            )

            with self.assertRaises(PermissionError):
                flow.apply(project_root, proposal)

            written = flow.apply(project_root, proposal.confirm())
            self.assertTrue((project_root / "AGENTS.md") in written)
            self.assertTrue((project_root / "docs" / "memoria" / "decisiones.md").exists())
            self.assertEqual(proposal.proposed.metadata.reviewed_commit, "def")
            self.assertEqual(len(proposal.changes), 1)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Protocol, Sequence

from factoria.domain.models import MemoryMetadata, ProjectMemory
from factoria.memory.filesystem import write_initial_memory
from factoria.memory.initializer import MemoryInitProposal, MemoryInitializer
from factoria.memory.renderer import render_agents_md, render_memory_document
from factoria.domain.models import MemoryDocumentKind, ProjectKind


class MemoryAnalyzer(Protocol):
    def analyze(self, project_root: Path, current: ProjectMemory) -> ProjectMemory: ...


@dataclass(frozen=True, slots=True)
class MemoryChange:
    target: str
    reason: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MemoryUpdateProposal:
    current: ProjectMemory
    proposed: ProjectMemory
    changes: tuple[MemoryChange, ...]
    confirmed: bool = False

    def confirm(self) -> "MemoryUpdateProposal":
        return replace(self, confirmed=True)


@dataclass(frozen=True, slots=True)
class MemoryInitFlow:
    initializer: MemoryInitializer

    def propose(
        self,
        project_root: Path,
        *,
        project_name: str,
        reviewed_commit: str,
        purpose: str = "",
        today: date | None = None,
    ) -> MemoryInitProposal:
        return self.initializer.propose(
            project_root,
            project_name=project_name,
            reviewed_commit=reviewed_commit,
            purpose=purpose,
            today=today,
        )

    def apply(self, project_root: Path, proposal: MemoryInitProposal):
        memory = self.initializer.require_confirmation(proposal)
        return write_initial_memory(project_root, memory)


@dataclass(frozen=True, slots=True)
class MemoryUpdateFlow:
    analyzer: MemoryAnalyzer
    factoria_version: str

    def propose(
        self,
        project_root: Path,
        current: ProjectMemory,
        *,
        reviewed_commit: str,
        changes: Sequence[MemoryChange],
        today: date | None = None,
    ) -> MemoryUpdateProposal:
        analyzed = self.analyzer.analyze(project_root, current)
        kind = (
            analyzed.metadata.project_kind
            if analyzed.metadata is not None
            else (current.metadata.project_kind if current.metadata else ProjectKind.MAINTENANCE)
        )
        proposed = replace(
            analyzed,
            metadata=MemoryMetadata(
                reviewed_commit=reviewed_commit,
                reviewed_at=today or date.today(),
                factoria_version=self.factoria_version,
                project_kind=kind,
            ),
        )
        return MemoryUpdateProposal(
            current=current,
            proposed=proposed,
            changes=tuple(changes),
        )

    def apply(self, project_root: Path, proposal: MemoryUpdateProposal) -> tuple[Path, ...]:
        if not proposal.confirmed:
            raise PermissionError("Memory update must be confirmed before writing project files")

        memory = proposal.proposed
        docs_root = project_root / "docs" / "memoria"
        docs_root.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []

        agents = project_root / "AGENTS.md"
        agents.write_text(render_agents_md(memory), encoding="utf-8", newline="")
        written.append(agents)

        kinds = [MemoryDocumentKind.TESTING]
        if memory.metadata and memory.metadata.project_kind is ProjectKind.ACTIVE:
            kinds.extend(
                [
                    MemoryDocumentKind.ARCHITECTURE,
                    MemoryDocumentKind.FLOWS,
                    MemoryDocumentKind.DECISIONS,
                ]
            )

        names = {
            MemoryDocumentKind.ARCHITECTURE: "arquitectura.md",
            MemoryDocumentKind.FLOWS: "flujos.md",
            MemoryDocumentKind.DECISIONS: "decisiones.md",
            MemoryDocumentKind.TESTING: "testing.md",
        }
        for kind in kinds:
            target = docs_root / names[kind]
            target.write_text(
                render_memory_document(memory, kind), encoding="utf-8", newline=""
            )
            written.append(target)
        return tuple(written)

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Protocol, Sequence

from factoria.domain.models import MemoryMetadata, ModuleMemory, ProjectKind, ProjectMemory


@dataclass(frozen=True, slots=True)
class GitActivitySnapshot:
    commits_last_30_days: int
    active_branches: int
    suggested_kind: ProjectKind


class TechnologyDetector(Protocol):
    def detect(self, project_root: Path) -> Sequence[str]: ...


class ModuleDetector(Protocol):
    def detect(self, project_root: Path) -> Sequence[ModuleMemory]: ...


class ActivityAnalyzer(Protocol):
    def analyze(self, project_root: Path) -> GitActivitySnapshot: ...


@dataclass(frozen=True, slots=True)
class MemoryInitProposal:
    memory: ProjectMemory
    activity: GitActivitySnapshot
    confirmed: bool = False

    def confirm(self) -> MemoryInitProposal:
        return replace(self, confirmed=True)


@dataclass(frozen=True, slots=True)
class MemoryInitializer:
    technology_detector: TechnologyDetector
    module_detector: ModuleDetector
    activity_analyzer: ActivityAnalyzer
    factoria_version: str

    def propose(
        self,
        project_root: Path,
        *,
        project_name: str,
        reviewed_commit: str,
        purpose: str = "",
        today: date | None = None,
    ) -> MemoryInitProposal:
        activity = self.activity_analyzer.analyze(project_root)
        technologies = tuple(dict.fromkeys(self.technology_detector.detect(project_root)))
        modules = tuple(self.module_detector.detect(project_root))

        memory = ProjectMemory(
            project_name=project_name,
            purpose=purpose,
            metadata=MemoryMetadata(
                reviewed_commit=reviewed_commit,
                reviewed_at=today or date.today(),
                factoria_version=self.factoria_version,
                project_kind=activity.suggested_kind,
            ),
            technologies=technologies,
            modules=modules,
        )
        return MemoryInitProposal(memory=memory, activity=activity)

    @staticmethod
    def require_confirmation(proposal: MemoryInitProposal) -> ProjectMemory:
        if not proposal.confirmed:
            raise PermissionError(
                "Memory initialization must be confirmed before writing project files"
            )
        return proposal.memory

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol, Sequence

from factoria.application.memory_flows import MemoryChange
from factoria.domain.models import ModuleMemory, ProjectMemory
from factoria.memory.git_staleness import MemoryStalenessReport


class TechnologyDetector(Protocol):
    def detect(self, project_root: Path) -> Sequence[str]: ...


class ModuleDetector(Protocol):
    def detect(self, project_root: Path) -> Sequence[ModuleMemory]: ...


@dataclass(frozen=True, slots=True)
class RepositoryMemoryAnalyzer:
    technology_detector: TechnologyDetector
    module_detector: ModuleDetector

    def analyze(self, project_root: Path, current: ProjectMemory) -> ProjectMemory:
        detected_technologies = tuple(self.technology_detector.detect(project_root))
        technologies = tuple(dict.fromkeys((*current.technologies, *detected_technologies)))

        existing = {module.name: module for module in current.modules}
        for detected in self.module_detector.detect(project_root):
            if detected.name not in existing:
                existing[detected.name] = detected
        modules = tuple(existing.values())
        return replace(current, technologies=technologies, modules=modules)


def describe_memory_changes(
    current: ProjectMemory,
    proposed: ProjectMemory,
    staleness: MemoryStalenessReport,
) -> tuple[MemoryChange, ...]:
    changes: list[MemoryChange] = []

    added_technologies = tuple(
        technology for technology in proposed.technologies if technology not in current.technologies
    )
    if added_technologies:
        changes.append(
            MemoryChange(
                target="technologies",
                reason="Se detectaron tecnologías presentes en el repositorio y ausentes de la memoria.",
                evidence=added_technologies,
            )
        )

    current_modules = {module.name for module in current.modules}
    added_modules = tuple(
        module.name for module in proposed.modules if module.name not in current_modules
    )
    if added_modules:
        changes.append(
            MemoryChange(
                target="modules",
                reason="Se detectaron módulos por estructura de carpetas que aún no estaban documentados.",
                evidence=added_modules,
            )
        )

    for document in staleness.stale_documents:
        changes.append(
            MemoryChange(
                target=f"memory:{document.value}",
                reason=(
                    f"La memoria supera su umbral de revisión: "
                    f"{staleness.commits_since_review} commits desde la última revisión "
                    f"(umbral {staleness.thresholds[document]})."
                ),
                evidence=(f"reviewed_commit={current.metadata.reviewed_commit if current.metadata else 'unknown'}",),
            )
        )

    if not changes:
        changes.append(
            MemoryChange(
                target="metadata",
                reason="Revisión completa sin cambios estructurales detectados; se actualizará la marca de revisión.",
                evidence=(f"commits_since_review={staleness.commits_since_review}",),
            )
        )

    return tuple(changes)

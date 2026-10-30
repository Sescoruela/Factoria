from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from factoria.domain.models import MemoryDocumentKind, ProjectKind, ProjectMemory

from .renderer import render_agents_md, render_memory_document


@dataclass(frozen=True, slots=True)
class WrittenMemoryFile:
    path: Path
    content: str


def memory_targets(project_root: Path, memory: ProjectMemory) -> tuple[Path, ...]:
    targets = [project_root / "AGENTS.md", project_root / "docs" / "memoria" / "testing.md"]
    if memory.metadata and memory.metadata.project_kind is ProjectKind.ACTIVE:
        targets.extend(
            [
                project_root / "docs" / "memoria" / "arquitectura.md",
                project_root / "docs" / "memoria" / "flujos.md",
                project_root / "docs" / "memoria" / "decisiones.md",
            ]
        )
    return tuple(targets)


def write_initial_memory(project_root: Path, memory: ProjectMemory) -> tuple[WrittenMemoryFile, ...]:
    """Write initial project memory without overwriting existing memory files."""
    project_root = project_root.resolve()
    targets = memory_targets(project_root, memory)
    existing = [path for path in targets if path.exists()]
    if existing:
        joined = ", ".join(str(path.relative_to(project_root)) for path in existing)
        raise FileExistsError(f"Initial memory would overwrite existing files: {joined}")

    documents: list[tuple[Path, str]] = [
        (project_root / "AGENTS.md", render_agents_md(memory)),
        (
            project_root / "docs" / "memoria" / "testing.md",
            render_memory_document(memory, MemoryDocumentKind.TESTING),
        ),
    ]

    if memory.metadata and memory.metadata.project_kind is ProjectKind.ACTIVE:
        documents.extend(
            [
                (
                    project_root / "docs" / "memoria" / "arquitectura.md",
                    render_memory_document(memory, MemoryDocumentKind.ARCHITECTURE),
                ),
                (
                    project_root / "docs" / "memoria" / "flujos.md",
                    render_memory_document(memory, MemoryDocumentKind.FLOWS),
                ),
                (
                    project_root / "docs" / "memoria" / "decisiones.md",
                    render_memory_document(memory, MemoryDocumentKind.DECISIONS),
                ),
            ]
        )

    written: list[WrittenMemoryFile] = []
    for path, content in documents:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")
        written.append(WrittenMemoryFile(path=path, content=content))
    return tuple(written)

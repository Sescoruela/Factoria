from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from factoria.domain.models import MemoryDocumentKind, ProjectMemory
from factoria.memory.staleness import DEFAULT_THRESHOLDS, MemoryStalenessPolicy


@dataclass(frozen=True, slots=True)
class MemoryStalenessReport:
    commits_since_review: int
    stale_documents: tuple[MemoryDocumentKind, ...]
    thresholds: Mapping[MemoryDocumentKind, int]

    @property
    def is_stale(self) -> bool:
        return bool(self.stale_documents)


@dataclass(frozen=True, slots=True)
class GitMemoryStalenessInspector:
    def inspect(
        self,
        project_root: Path,
        memory: ProjectMemory,
        *,
        threshold_overrides: Mapping[MemoryDocumentKind, int] | None = None,
    ) -> MemoryStalenessReport:
        if memory.metadata is None:
            raise ValueError("Project memory has no review metadata")
        root = project_root.resolve()
        reviewed_commit = memory.metadata.reviewed_commit
        self._ensure_commit_exists(root, reviewed_commit)
        commits = int(
            self._git(root, "rev-list", "--count", f"{reviewed_commit}..HEAD").strip() or "0"
        )
        thresholds = dict(DEFAULT_THRESHOLDS)
        if threshold_overrides:
            thresholds.update(threshold_overrides)
        policy = MemoryStalenessPolicy(thresholds=MappingProxyType(thresholds))
        counts = {document: commits for document in thresholds}
        return MemoryStalenessReport(
            commits_since_review=commits,
            stale_documents=policy.stale_documents(counts),
            thresholds=MappingProxyType(thresholds),
        )

    @classmethod
    def _ensure_commit_exists(cls, root: Path, commit: str) -> None:
        try:
            cls._git(root, "cat-file", "-e", f"{commit}^{{commit}}")
        except subprocess.CalledProcessError as exc:
            raise ValueError(
                f"Reviewed commit {commit!r} is not available in this repository"
            ) from exc

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

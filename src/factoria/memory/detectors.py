from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from factoria.domain.models import ModuleMemory, ProjectKind

from .initializer import GitActivitySnapshot


@dataclass(frozen=True, slots=True)
class BasicTechnologyDetector:
    """Conservative, dependency-free technology detection for memoria-init proposals."""

    def detect(self, project_root: Path) -> tuple[str, ...]:
        technologies: list[str] = []

        if any(project_root.glob("*.sln")) or any(project_root.rglob("*.csproj")):
            technologies.append("dotnet")
        if (project_root / "angular.json").exists() or any(project_root.rglob("angular.json")):
            technologies.append("angular")
        if (project_root / "package.json").exists() or any(project_root.rglob("package.json")):
            technologies.append("javascript-typescript")
        if (
            (project_root / "pyproject.toml").exists()
            or (project_root / "requirements.txt").exists()
            or any(project_root.glob("requirements*.txt"))
        ):
            technologies.append("python")

        return tuple(dict.fromkeys(technologies))


@dataclass(frozen=True, slots=True)
class DirectoryModuleDetector:
    candidate_names: tuple[str, ...] = (
        "backend",
        "frontend",
        "api",
        "web",
        "src",
        "packages",
        "apps",
        "shared",
        "common",
        "contracts",
    )

    def detect(self, project_root: Path) -> tuple[ModuleMemory, ...]:
        modules: list[ModuleMemory] = []
        for name in self.candidate_names:
            path = project_root / name
            if path.is_dir():
                modules.append(ModuleMemory(name=name, paths=(f"{name}/",)))
        return tuple(modules)


@dataclass(frozen=True, slots=True)
class GitActivityAnalyzer:
    window_days: int = 30
    min_commits_for_active: int = 4
    min_branches_for_active: int = 2

    def analyze(self, project_root: Path) -> GitActivitySnapshot:
        commits = int(
            self._git(
                project_root,
                "rev-list",
                "--count",
                f"--since={self.window_days} days ago",
                "HEAD",
            ).strip()
            or "0"
        )
        branches = tuple(
            line.strip()
            for line in self._git(
                project_root,
                "for-each-ref",
                "--format=%(refname:short)",
                "refs/heads/",
            ).splitlines()
            if line.strip()
        )
        suggested = (
            ProjectKind.ACTIVE
            if commits >= self.min_commits_for_active
            or len(branches) >= self.min_branches_for_active
            else ProjectKind.MAINTENANCE
        )
        return GitActivitySnapshot(
            commits_last_30_days=commits,
            active_branches=len(branches),
            suggested_kind=suggested,
        )

    @staticmethod
    def _git(project_root: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(project_root), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return completed.stdout

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class UiWorkspaceSettings:
    projects_root: Path | None = None
    last_project: Path | None = None

    @classmethod
    def load(cls, path: Path | None = None) -> "UiWorkspaceSettings":
        target = path or (Path.home() / ".factoria" / "ui.json")
        if not target.exists():
            return cls()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        root_raw = data.get("projects_root")
        project_raw = data.get("last_project")
        return cls(
            projects_root=Path(root_raw).expanduser() if root_raw else None,
            last_project=Path(project_raw).expanduser() if project_raw else None,
        )

    def save(self, path: Path | None = None) -> None:
        target = path or (Path.home() / ".factoria" / "ui.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "projects_root": str(self.projects_root) if self.projects_root else None,
                    "last_project": str(self.last_project) if self.last_project else None,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


_IGNORED_DISCOVERY_DIRS = {
    ".git",
    ".factoria",
    ".venv",
    "venv",
    "node_modules",
    "bin",
    "obj",
    "dist",
    "build",
    "vendor",
}


def _has_git_marker(path: Path) -> bool:
    marker = path / ".git"
    if marker.is_dir():
        return True
    if not marker.is_file():
        return False
    try:
        with marker.open(encoding="utf-8") as handle:
            line = handle.readline(4096).strip()
        if not line.startswith("gitdir:"):
            return False
        target = line[len("gitdir:"):].strip()
        if not target:
            return False
        metadata = Path(target)
        if not metadata.is_absolute():
            metadata = path / metadata
        return metadata.is_dir()
    except (OSError, UnicodeError):
        return False


def project_root(path: Path, workspace_root: Path | None = None) -> Path | None:
    """Map a selected folder to the first repository within its workspace.

    Nested repositories/submodules belong to their containing project in the list.
    With no workspace boundary, return the nearest enclosing repository. This also
    supports explicitly choosing a nested repository as the workspace itself.
    """
    path = path.expanduser().resolve()
    if not path.is_dir():
        return None
    ancestors = (path, *path.parents)
    candidates = [parent for parent in ancestors if _has_git_marker(parent)]
    if workspace_root is not None:
        boundary = workspace_root.expanduser().resolve()
        inside = [candidate for candidate in candidates if candidate.is_relative_to(boundary)]
        if inside:
            return inside[-1]
    return candidates[0] if candidates else None


def discover_projects(root: Path) -> tuple[Path, ...]:
    """Return one entry per outer repository within the configured workspace.

    Recurse through grouping folders, but stop at a project boundary. Repositories
    inside a project are modules/dependencies, not additional list entries. Starting
    inside a repository returns its owning root. External sibling worktrees remain
    distinct projects. No coding tool or Git subprocess is started by discovery.
    """
    root = root.expanduser().resolve()
    if not root.is_dir():
        return ()
    owner = project_root(root)
    if owner is not None:
        return (owner,)

    projects: list[Path] = []
    seen: set[Path] = set()
    for current, dirs, _files in os.walk(root):
        current_path = Path(current)
        dirs[:] = [name for name in dirs if name not in _IGNORED_DISCOVERY_DIRS]
        if _has_git_marker(current_path):
            resolved = current_path.resolve()
            if resolved not in seen:
                projects.append(resolved)
                seen.add(resolved)
            dirs[:] = []

    return tuple(sorted(projects, key=lambda path: str(path).lower()))


def choose_folder(initial: Path | None = None) -> Path | None:
    """Open the native Tk folder picker when available; callers provide a text fallback."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        window = tk.Tk()
        window.withdraw()
        window.attributes("-topmost", True)
        selected = filedialog.askdirectory(
            title="Selecciona la carpeta raíz de proyectos de Factoria",
            initialdir=str(initial) if initial and initial.exists() else None,
            mustexist=True,
        )
        window.destroy()
    except Exception:
        return None
    return Path(selected).expanduser().resolve() if selected else None

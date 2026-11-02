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


def discover_projects(root: Path) -> tuple[Path, ...]:
    """Return every Git repository below the configured project root.

    Discovery is recursive so projects can be grouped in subfolders. Heavy generated
    directories are pruned, but there is no artificial result limit.
    """
    root = root.expanduser().resolve()
    if not root.is_dir():
        return ()

    projects: list[Path] = []
    seen: set[Path] = set()
    for current, dirs, _files in os.walk(root):
        current_path = Path(current)
        dirs[:] = [name for name in dirs if name not in _IGNORED_DISCOVERY_DIRS]
        git_marker = current_path / ".git"
        if git_marker.exists():
            resolved = current_path.resolve()
            if resolved not in seen:
                projects.append(resolved)
                seen.add(resolved)

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

from __future__ import annotations

import json
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


def discover_projects(root: Path) -> tuple[Path, ...]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        return ()
    projects: list[Path] = []
    if (root / ".git").exists():
        projects.append(root)
    try:
        children = sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name.lower())
    except OSError:
        return tuple(projects)
    for child in children:
        if (child / ".git").exists():
            projects.append(child.resolve())
    return tuple(projects)


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

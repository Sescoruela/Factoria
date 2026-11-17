from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


_LOCAL_EXCLUDE_MARKER = "# factoria: local runtime artifacts"
_LOCAL_WORK_RULE = "/.factoria/work/"


def ensure_local_runtime_excluded(project_root: Path) -> None:
    """Keep Factoria's transient workspace out of Git without editing .gitignore.

    Non-Git directories remain supported: in that case this is intentionally a no-op.
    """
    completed = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "--git-path", "info/exclude"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return

    exclude_path = Path(completed.stdout.strip())
    if not exclude_path.is_absolute():
        exclude_path = project_root / exclude_path
    exclude_path = exclude_path.resolve()
    exclude_path.parent.mkdir(parents=True, exist_ok=True)

    existing = ""
    if exclude_path.exists():
        existing = exclude_path.read_text(encoding="utf-8", errors="replace")
        if any(line.strip() == _LOCAL_WORK_RULE for line in existing.splitlines()):
            return

    newline = "\r\n" if "\r\n" in existing else "\n"
    prefix = ""
    if existing and not existing.endswith(("\n", "\r")):
        prefix = newline
    addition = f"{prefix}{_LOCAL_EXCLUDE_MARKER}{newline}{_LOCAL_WORK_RULE}{newline}"
    with exclude_path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(addition)


@dataclass(frozen=True, slots=True)
class FlowWorkspace:
    flow_id: str
    root: Path

    @property
    def task_file(self) -> Path:
        return self.root / "task.md"

    @property
    def plan_file(self) -> Path:
        return self.root / "plan.md"

    @property
    def review_file(self) -> Path:
        return self.root / "review.md"

    @property
    def state_file(self) -> Path:
        return self.root / "state.toml"


@dataclass(frozen=True, slots=True)
class FlowArtifactStore:
    project_root: Path

    @property
    def work_root(self) -> Path:
        return self.project_root / ".factoria" / "work"

    def workspace(self, flow_id: str) -> FlowWorkspace:
        return FlowWorkspace(flow_id=flow_id, root=self.work_root / flow_id)

    def ensure(self, flow_id: str) -> FlowWorkspace:
        ensure_local_runtime_excluded(self.project_root)
        workspace = self.workspace(flow_id)
        workspace.root.mkdir(parents=True, exist_ok=True)
        return workspace

    def write_text(self, flow_id: str, filename: str, content: str) -> Path:
        workspace = self.ensure(flow_id)
        target = workspace.root / filename
        target.write_text(content, encoding="utf-8", newline="")
        return target

    def cleanup(self, flow_id: str) -> None:
        workspace = self.workspace(flow_id)
        if not workspace.root.exists():
            return
        for path in sorted(workspace.root.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        workspace.root.rmdir()

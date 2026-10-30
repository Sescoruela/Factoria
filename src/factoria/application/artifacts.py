from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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

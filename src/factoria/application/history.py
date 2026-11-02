from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Mapping

from .final_report import parse_agent_metrics, render_final_report
from .flow_service import FlowExecution


@dataclass(frozen=True, slots=True)
class HistoryRecord:
    flow_id: str
    kind: str
    state: str
    label: str | None
    branch: str | None
    commit_sha: str | None
    started_at: str | None
    ended_at: str
    duration_seconds: float | None
    artifacts: Mapping[str, str]
    permission_profile: str | None = None
    permission_escalated: bool = False
    transitions: tuple[Mapping[str, str | None], ...] = field(default_factory=tuple)
    agent_attempts: int = 0
    agent_fallbacks: int = 0
    agent_adapters: tuple[str, ...] = field(default_factory=tuple)
    agent_models: tuple[str, ...] = field(default_factory=tuple)
    usage_source: str = "unavailable"
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


@dataclass(frozen=True, slots=True)
class LocalExecutionHistoryStore:
    project_root: Path
    max_records: int = 50
    max_age_days: int = 30
    max_artifact_chars: int = 100_000

    def history_root(self) -> Path:
        completed = subprocess.run(
            ["git", "-C", str(self.project_root), "rev-parse", "--git-path", "factoria/history"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        path = Path(completed.stdout.strip())
        if not path.is_absolute():
            path = self.project_root / path
        return path.resolve()

    def snapshot(self, workspace: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        if not workspace.exists():
            return result
        allowed = {
            "task.md",
            "plan.md",
            "verification.md",
            "review.md",
            "memory-proposal.md",
            "agents.log",
            "agent-flow.json",
            "permissions.json",
            "state.toml",
            "manual-verification.json",
            "commit.json",
            "security-incident.json",
            "impact.md",
            "external-impact-review.json",
        }
        for path in sorted(workspace.iterdir()):
            if not path.is_file():
                continue
            dynamic = (
                path.name.startswith("review-cycle-")
                or path.name.startswith("correction-")
                or "security" in path.name.lower()
                or "secret" in path.name.lower()
            )
            if path.name not in allowed and not dynamic:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            result[path.name] = text[-self.max_artifact_chars :]
        return result

    def archive(
        self,
        execution: FlowExecution,
        *,
        artifacts: Mapping[str, str],
        branch: str | None = None,
        commit_sha: str | None = None,
        ended_at: datetime | None = None,
    ) -> HistoryRecord:
        ended = ended_at or datetime.now(UTC)
        started = execution.flow.history[0].occurred_at if execution.flow.history else None
        duration = (ended - started).total_seconds() if started is not None else None
        permission_profile = None
        permission_escalated = False
        raw_permissions = artifacts.get("permissions.json")
        if raw_permissions:
            try:
                permissions = json.loads(raw_permissions)
                permission_profile = permissions.get("effective_profile")
                permission_escalated = bool(permissions.get("temporary_escalation", False))
            except (json.JSONDecodeError, TypeError):
                pass

        metrics = parse_agent_metrics(artifacts.get("agents.log", ""))
        transitions = tuple(
            {
                "source": item.source.value,
                "target": item.target.value,
                "occurred_at": item.occurred_at.isoformat(),
                "reason": item.reason,
            }
            for item in execution.flow.history
        )
        record = HistoryRecord(
            flow_id=execution.flow.flow_id,
            kind=execution.flow.kind,
            state=execution.flow.state.value,
            label=execution.label,
            branch=branch,
            commit_sha=commit_sha,
            started_at=started.isoformat() if started else None,
            ended_at=ended.isoformat(),
            duration_seconds=duration,
            artifacts=dict(artifacts),
            permission_profile=permission_profile,
            permission_escalated=permission_escalated,
            transitions=transitions,
            agent_attempts=metrics.attempts,
            agent_fallbacks=metrics.fallback_attempts,
            agent_adapters=metrics.adapters,
            agent_models=metrics.models,
            usage_source=metrics.usage_source,
            input_tokens=metrics.input_tokens,
            output_tokens=metrics.output_tokens,
            cost_usd=metrics.cost_usd,
        )
        root = self.history_root()
        root.mkdir(parents=True, exist_ok=True)
        target = root / f"{execution.flow.flow_id}.json"
        target.write_text(
            json.dumps(asdict(record), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (root / f"{execution.flow.flow_id}.txt").write_text(
            self.render_report(record), encoding="utf-8", newline=""
        )
        self.prune(now=ended)
        return record

    def list(
        self,
        *,
        kind: str | None = None,
        state: str | None = None,
        limit: int | None = None,
    ) -> tuple[HistoryRecord, ...]:
        root = self.history_root()
        if not root.exists():
            return ()
        records: list[HistoryRecord] = []
        for path in root.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            record = HistoryRecord(**data)
            if kind is not None and record.kind != kind:
                continue
            if state is not None and record.state != state:
                continue
            records.append(record)
        records.sort(key=lambda item: item.ended_at, reverse=True)
        if limit is not None:
            records = records[: max(0, limit)]
        return tuple(records)

    def prune(self, *, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        cutoff = now - timedelta(days=self.max_age_days)
        records = list(self.list())
        keep_ids: set[str] = set()
        for record in records:
            ended = datetime.fromisoformat(record.ended_at)
            if ended >= cutoff and len(keep_ids) < self.max_records:
                keep_ids.add(record.flow_id)
        root = self.history_root()
        for path in root.glob("*.json"):
            if path.stem not in keep_ids:
                path.unlink(missing_ok=True)
                (root / f"{path.stem}.txt").unlink(missing_ok=True)

    @staticmethod
    def render_report(record: HistoryRecord) -> str:
        return render_final_report(record)

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class AgentMetrics:
    attempts: int = 0
    fallback_attempts: int = 0
    adapters: tuple[str, ...] = ()
    models: tuple[str, ...] = ()
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    usage_source: str = "unavailable"

    @property
    def has_usage(self) -> bool:
        return any(
            value is not None
            for value in (self.input_tokens, self.output_tokens, self.cost_usd)
        )


def parse_agent_metrics(text: str) -> AgentMetrics:
    attempts = 0
    fallback_attempts = 0
    adapters: list[str] = []
    models: list[str] = []
    input_tokens = 0
    output_tokens = 0
    cost_usd = 0.0
    usage_seen = False
    sources: set[str] = set()

    for raw in text.splitlines():
        if not raw.strip():
            continue
        fields = dict(re.findall(r"([a-z_]+)=([^\s]+)", raw))
        if "attempt" not in fields or "adapter" not in fields:
            continue
        attempts += 1
        adapter = fields["adapter"]
        if adapter not in adapters:
            adapters.append(adapter)
        model = fields.get("model")
        if model and model != "default" and model not in models:
            models.append(model)
        if fields.get("fallback", "false").lower() == "true":
            fallback_attempts += 1

        source = fields.get("metrics_source")
        if source in {"real", "estimated"}:
            sources.add(source)
        for key in ("input_tokens", "output_tokens"):
            value = fields.get(key)
            if value is None:
                continue
            try:
                parsed = int(value)
            except ValueError:
                continue
            usage_seen = True
            if key == "input_tokens":
                input_tokens += parsed
            else:
                output_tokens += parsed
        if "cost_usd" in fields:
            try:
                cost_usd += float(fields["cost_usd"])
                usage_seen = True
            except ValueError:
                pass

    if not usage_seen:
        usage_source = "unavailable"
        in_value = out_value = None
        cost_value = None
    else:
        usage_source = "estimated" if "estimated" in sources else "real"
        in_value = input_tokens
        out_value = output_tokens
        cost_value = cost_usd

    return AgentMetrics(
        attempts=attempts,
        fallback_attempts=fallback_attempts,
        adapters=tuple(adapters),
        models=tuple(models),
        input_tokens=in_value,
        output_tokens=out_value,
        cost_usd=cost_value,
        usage_source=usage_source,
    )


def render_final_report(record) -> str:
    artifacts: Mapping[str, str] = record.artifacts
    objective = _objective(artifacts.get("task.md", ""))
    changes = _commit_changes(artifacts.get("commit.json"))
    verification = _summary_lines(artifacts.get("verification.md", ""), limit=12)
    review_name = _latest_review_name(artifacts)
    review = _summary_lines(artifacts.get(review_name, ""), limit=14) if review_name else ()
    security = _security_summary(artifacts)
    metrics = parse_agent_metrics(artifacts.get("agents.log", ""))

    duration = (
        f"{record.duration_seconds:.1f}s"
        if record.duration_seconds is not None
        else "not available"
    )
    lines = [
        "FACTORIA FINAL REPORT",
        "",
        "Summary",
        f"- flow_id: {record.flow_id}",
        f"- kind: {record.kind}",
        f"- state: {record.state}",
        f"- objective: {objective or record.label or '-'}",
        f"- branch: {record.branch or '-'}",
        f"- commit: {record.commit_sha or '-'}",
        f"- duration: {duration}",
        "",
        "Changes",
    ]
    if changes:
        lines.extend(f"- {item}" for item in changes)
    else:
        lines.append("- No persisted commit/change summary is available.")

    lines.extend(["", "Verification"])
    lines.extend(f"- {item}" for item in verification) if verification else lines.append(
        "- No persisted verification evidence is available."
    )

    lines.extend(["", "Review"])
    lines.extend(f"- {item}" for item in review) if review else lines.append(
        "- No persisted structured review evidence is available."
    )

    lines.extend(["", "Security"])
    lines.extend(f"- {item}" for item in security)

    lines.extend(
        [
            "",
            "Permissions",
            f"- effective_profile: {record.permission_profile or '-'}",
            f"- temporary_escalation: {str(record.permission_escalated).lower()}",
            "",
            "Agent metrics",
            f"- attempts: {metrics.attempts}",
            f"- fallback_attempts: {metrics.fallback_attempts}",
            f"- adapters: {', '.join(metrics.adapters) or '-'}",
            f"- models: {', '.join(metrics.models) or '-'}",
            f"- usage_source: {metrics.usage_source}",
        ]
    )
    if metrics.has_usage:
        lines.extend(
            [
                f"- input_tokens: {metrics.input_tokens if metrics.input_tokens is not None else '-'}",
                f"- output_tokens: {metrics.output_tokens if metrics.output_tokens is not None else '-'}",
                f"- cost_usd: {metrics.cost_usd:.6f}" if metrics.cost_usd is not None else "- cost_usd: -",
            ]
        )
    else:
        lines.append("- token/cost metrics: not exposed by the persisted adapter evidence; not estimated.")

    recommendation = _profile_recommendation(metrics)
    lines.extend(["", "Recommendation", f"- {recommendation}"])

    lines.extend(["", "State history"])
    transitions: Sequence[Mapping[str, str | None]] = getattr(record, "transitions", ())
    if transitions:
        for item in transitions:
            reason = item.get("reason")
            suffix = f" | {reason}" if reason else ""
            lines.append(
                f"- {item.get('occurred_at', '-')} | {item.get('source', '-')} -> {item.get('target', '-')}{suffix}"
            )
    else:
        lines.append("- No persisted transition history is available.")

    return "\n".join(lines) + "\n"


def _objective(text: str) -> str | None:
    for raw in text.splitlines():
        value = raw.strip()
        if value and not value.startswith("#"):
            return value
    return None


def _commit_changes(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ()
    result: list[str] = []
    message = data.get("message")
    if isinstance(message, str) and message:
        result.append(f"commit message: {message}")
    files = data.get("files", [])
    if isinstance(files, list):
        for path in files:
            if isinstance(path, str) and path:
                result.append(path)
    return tuple(result)


def _latest_review_name(artifacts: Mapping[str, str]) -> str | None:
    cycle_names = sorted(
        (
            name
            for name in artifacts
            if name.startswith("review-cycle-") and name.endswith(".md")
        ),
        key=lambda name: int(re.search(r"(\d+)", name).group(1)) if re.search(r"(\d+)", name) else 0,
    )
    if cycle_names:
        return cycle_names[-1]
    return "review.md" if "review.md" in artifacts else None


def _summary_lines(text: str, *, limit: int) -> tuple[str, ...]:
    result: list[str] = []
    for raw in text.splitlines():
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        value = value.lstrip("- ").strip()
        if value:
            result.append(value)
        if len(result) >= limit:
            break
    return tuple(result)


def _security_summary(artifacts: Mapping[str, str]) -> tuple[str, ...]:
    candidates = [
        name
        for name in artifacts
        if "security" in name.lower() or "secret" in name.lower()
    ]
    if not candidates:
        return ("No persisted security incident evidence for this execution.",)
    result: list[str] = []
    for name in sorted(candidates):
        text = artifacts[name]
        lowered = text.lower()
        if "redacted" in lowered or "fingerprint" in lowered or "incident" in lowered:
            result.append(f"Sanitized security evidence archived in {name}.")
        else:
            result.append(f"Security-related artifact archived in {name}.")
    result.append("Secret values are never reproduced in this report.")
    return tuple(result)


def _profile_recommendation(metrics: AgentMetrics) -> str:
    if metrics.attempts == 0:
        return "No model/profile recommendation: no agent-attempt evidence is available."
    if metrics.fallback_attempts >= 2:
        return (
            "Consider reviewing the configured model/tool profile because repeated fallbacks were observed; "
            "Factoria will not change it automatically."
        )
    return (
        "Keep the current profile unless repeated execution history shows a clear quality/cost trade-off; "
        "Factoria does not switch profiles automatically."
    )

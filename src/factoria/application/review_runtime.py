from __future__ import annotations

import json
from dataclasses import dataclass

from factoria.domain.fix import (
    FindingSeverity,
    ReviewFinding,
    ReviewResult,
)


class ReviewParseError(ValueError):
    """Raised when reviewer output does not satisfy the structured contract."""


@dataclass(frozen=True, slots=True)
class StructuredReview:
    result: str
    review: ReviewResult
    risks: tuple[str, ...]
    recommendation: str

    @property
    def blocks_closure(self) -> bool:
        return self.review.blocks_closure


def parse_structured_review(text: str) -> StructuredReview:
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            raw = "\n".join(lines[1:-1])
            if raw.lstrip().startswith("json"):
                raw = raw.lstrip()[4:].lstrip("\n")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReviewParseError(f"Reviewer output is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ReviewParseError("Reviewer output must be a JSON object")

    result = data.get("result")
    if result not in {"approved", "changes_required"}:
        raise ReviewParseError("result must be 'approved' or 'changes_required'")

    acceptance = data.get("acceptance_criteria_met")
    if not isinstance(acceptance, bool):
        raise ReviewParseError("acceptance_criteria_met must be boolean")

    violations = _string_list(data.get("mandatory_rules_violated"), "mandatory_rules_violated")
    risks = _string_list(data.get("risks"), "risks")
    recommendation = data.get("recommendation")
    if not isinstance(recommendation, str) or not recommendation.strip():
        raise ReviewParseError("recommendation must be a non-empty string")

    findings_raw = data.get("findings")
    if not isinstance(findings_raw, list):
        raise ReviewParseError("findings must be a list")
    findings: list[ReviewFinding] = []
    for index, item in enumerate(findings_raw):
        if not isinstance(item, dict):
            raise ReviewParseError(f"findings[{index}] must be an object")
        severity_raw = item.get("severity")
        try:
            severity = FindingSeverity(severity_raw)
        except (TypeError, ValueError) as exc:
            raise ReviewParseError(
                f"findings[{index}].severity must be critical, important or minor"
            ) from exc
        message = item.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ReviewParseError(f"findings[{index}].message must be non-empty")
        rule = item.get("rule")
        if rule is not None and (not isinstance(rule, str) or not rule.strip()):
            raise ReviewParseError(f"findings[{index}].rule must be null or non-empty")
        findings.append(
            ReviewFinding(
                severity=severity,
                message=message.strip(),
                rule=rule.strip() if isinstance(rule, str) else None,
            )
        )

    review = ReviewResult(
        findings=tuple(findings),
        mandatory_rules_violated=violations,
        acceptance_criteria_met=acceptance,
    )
    expected_result = "changes_required" if review.blocks_closure else "approved"
    if result != expected_result:
        raise ReviewParseError(
            f"result={result!r} contradicts the structured findings; expected {expected_result!r}"
        )
    return StructuredReview(
        result=result,
        review=review,
        risks=risks,
        recommendation=recommendation.strip(),
    )


def render_structured_review(review: StructuredReview) -> str:
    payload = {
        "result": review.result,
        "acceptance_criteria_met": review.review.acceptance_criteria_met,
        "mandatory_rules_violated": list(review.review.mandatory_rules_violated),
        "findings": [
            {
                "severity": finding.severity.value,
                "message": finding.message,
                "rule": finding.rule,
            }
            for finding in review.review.findings
        ],
        "risks": list(review.risks),
        "recommendation": review.recommendation,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _string_list(value, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ReviewParseError(f"{field} must be a list of non-empty strings")
    return tuple(item.strip() for item in value)

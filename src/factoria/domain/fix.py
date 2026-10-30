from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ReproductionKind(StrEnum):
    AUTOMATED_TEST = "automated_test"
    SCRIPT = "script"
    MANUAL = "manual"


class FixPhase(StrEnum):
    REPRODUCE = "reproduce"
    ANALYZE = "analyze"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    IMPLEMENT = "implement"
    VERIFY = "verify"
    REVIEW = "review"
    CORRECTION = "correction"
    AWAITING_FINAL_APPROVAL = "awaiting_final_approval"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class FindingSeverity(StrEnum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    MINOR = "minor"


@dataclass(frozen=True, slots=True)
class FixLimits:
    max_files: int = 5
    max_changed_lines: int = 200
    max_review_cycles: int = 2


@dataclass(frozen=True, slots=True)
class FixTask:
    task_id: str
    title: str
    description: str
    acceptance_criteria: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ReproductionEvidence:
    kind: ReproductionKind
    description: str
    command: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class ChangeScope:
    files_changed: int
    lines_changed: int

    def is_large(self, limits: FixLimits) -> bool:
        return self.files_changed > limits.max_files or self.lines_changed > limits.max_changed_lines


@dataclass(frozen=True, slots=True)
class VerificationResult:
    name: str
    passed: bool
    required: bool
    details: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    severity: FindingSeverity
    message: str
    rule: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewResult:
    findings: tuple[ReviewFinding, ...] = field(default_factory=tuple)
    mandatory_rules_violated: tuple[str, ...] = field(default_factory=tuple)
    acceptance_criteria_met: bool = True

    @property
    def blocking_findings(self) -> tuple[ReviewFinding, ...]:
        return tuple(
            finding
            for finding in self.findings
            if finding.severity in {FindingSeverity.CRITICAL, FindingSeverity.IMPORTANT}
        )

    @property
    def blocks_closure(self) -> bool:
        return bool(
            self.blocking_findings
            or self.mandatory_rules_violated
            or not self.acceptance_criteria_met
        )

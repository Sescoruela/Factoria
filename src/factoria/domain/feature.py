from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .fix import ReviewResult, VerificationResult


class FeaturePhase(StrEnum):
    DEFINE = "define"
    PLAN = "plan"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    IMPLEMENT = "implement"
    VERIFY = "verify"
    REVIEW = "review"
    MEMORY_UPDATE = "memory_update"
    AWAITING_FINAL_APPROVAL = "awaiting_final_approval"
    BLOCKED = "blocked"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class AcceptanceCriterion:
    description: str
    functional: bool = True


@dataclass(frozen=True, slots=True)
class FeatureTask:
    task_id: str
    title: str
    description: str
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class FeaturePlan:
    summary: str
    steps: tuple[str, ...]
    risks: tuple[str, ...] = field(default_factory=tuple)
    affected_modules: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class FeatureOutcome:
    verifications: tuple[VerificationResult, ...] = field(default_factory=tuple)
    review: ReviewResult = field(default_factory=ReviewResult)
    memory_update_required: bool = False

    @property
    def required_verifications_passed(self) -> bool:
        return all(result.passed for result in self.verifications if result.required)

    @property
    def can_close(self) -> bool:
        return self.required_verifications_passed and not self.review.blocks_closure

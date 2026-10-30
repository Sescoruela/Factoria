from __future__ import annotations

from dataclasses import dataclass, field, replace

from factoria.domain.fix import (
    ChangeScope,
    FixLimits,
    FixPhase,
    FixTask,
    ReproductionEvidence,
    ReviewResult,
    VerificationResult,
)

from .quality import ReviewAction, ReviewGate, VerificationGate


class FixFlowError(RuntimeError):
    """Raised when a fix flow receives an invalid action for its current phase."""


@dataclass(frozen=True, slots=True)
class FixRun:
    task: FixTask
    limits: FixLimits = field(default_factory=FixLimits)
    phase: FixPhase = FixPhase.REPRODUCE
    reproduction: ReproductionEvidence | None = None
    scope: ChangeScope | None = None
    verification: tuple[VerificationResult, ...] = field(default_factory=tuple)
    review: ReviewResult | None = None
    review_cycle: int = 0
    promoted_to_large: bool = False
    block_reason: str | None = None

    def _require(self, *phases: FixPhase) -> None:
        if self.phase not in phases:
            allowed = ", ".join(phase.value for phase in phases)
            raise FixFlowError(f"Action requires phase [{allowed}], current={self.phase.value}")

    def record_reproduction(self, evidence: ReproductionEvidence) -> FixRun:
        self._require(FixPhase.REPRODUCE)
        if not evidence.description.strip():
            raise FixFlowError("Reproduction evidence must describe how the bug is reproduced")
        return replace(self, reproduction=evidence, phase=FixPhase.ANALYZE)

    def assess_scope(self, scope: ChangeScope) -> FixRun:
        self._require(FixPhase.ANALYZE)
        if scope.files_changed < 0 or scope.lines_changed < 0:
            raise FixFlowError("Change scope values cannot be negative")
        is_large = scope.is_large(self.limits)
        return replace(
            self,
            scope=scope,
            promoted_to_large=is_large,
            phase=FixPhase.AWAITING_PLAN_APPROVAL if is_large else FixPhase.IMPLEMENT,
        )

    def approve_large_plan(self) -> FixRun:
        self._require(FixPhase.AWAITING_PLAN_APPROVAL)
        return replace(self, phase=FixPhase.IMPLEMENT)

    def implementation_completed(self) -> FixRun:
        self._require(FixPhase.IMPLEMENT, FixPhase.CORRECTION)
        return replace(self, phase=FixPhase.VERIFY)

    def record_verification(self, results: tuple[VerificationResult, ...]) -> FixRun:
        self._require(FixPhase.VERIFY)
        decision = VerificationGate.evaluate(results)
        if not decision.passed:
            return replace(
                self,
                verification=results,
                phase=FixPhase.BLOCKED,
                block_reason=decision.reason,
            )
        return replace(self, verification=results, phase=FixPhase.REVIEW, block_reason=None)

    def record_review(self, result: ReviewResult) -> FixRun:
        self._require(FixPhase.REVIEW)
        decision = ReviewGate(self.limits.max_review_cycles).evaluate(
            result,
            current_cycle=self.review_cycle,
        )
        if decision.action is ReviewAction.CORRECT:
            return replace(
                self,
                review=result,
                review_cycle=decision.next_cycle,
                phase=FixPhase.CORRECTION,
                block_reason=None,
            )
        if decision.action is ReviewAction.BLOCK:
            return replace(
                self,
                review=result,
                review_cycle=decision.next_cycle,
                phase=FixPhase.BLOCKED,
                block_reason=decision.reason,
            )

        final_phase = (
            FixPhase.AWAITING_FINAL_APPROVAL if self.promoted_to_large else FixPhase.COMPLETED
        )
        return replace(
            self,
            review=result,
            review_cycle=decision.next_cycle,
            phase=final_phase,
            block_reason=None,
        )

    def approve_final(self) -> FixRun:
        self._require(FixPhase.AWAITING_FINAL_APPROVAL)
        return replace(self, phase=FixPhase.COMPLETED)

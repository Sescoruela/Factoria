from __future__ import annotations

from dataclasses import dataclass, replace

from factoria.domain.feature import FeatureOutcome, FeaturePhase, FeaturePlan, FeatureTask


class FeatureFlowError(RuntimeError):
    """Raised when a feature flow violates its governance gates."""


@dataclass(frozen=True, slots=True)
class FeatureRun:
    task: FeatureTask
    phase: FeaturePhase = FeaturePhase.DEFINE
    plan: FeaturePlan | None = None
    plan_approved: bool = False
    memory_update_confirmed: bool = False
    final_approved: bool = False
    outcome: FeatureOutcome | None = None

    def propose_plan(self, plan: FeaturePlan) -> FeatureRun:
        if not self.task.acceptance_criteria:
            raise FeatureFlowError("Feature requires acceptance criteria before planning")
        return replace(self, plan=plan, phase=FeaturePhase.AWAITING_PLAN_APPROVAL)

    def approve_plan(self) -> FeatureRun:
        if self.phase is not FeaturePhase.AWAITING_PLAN_APPROVAL or self.plan is None:
            raise FeatureFlowError("No feature plan is awaiting approval")
        return replace(self, plan_approved=True, phase=FeaturePhase.IMPLEMENT)

    def record_outcome(self, outcome: FeatureOutcome) -> FeatureRun:
        if self.phase is not FeaturePhase.IMPLEMENT or not self.plan_approved:
            raise FeatureFlowError("Implementation requires an approved plan")
        if not outcome.required_verifications_passed:
            return replace(self, outcome=outcome, phase=FeaturePhase.BLOCKED)
        if outcome.review.blocks_closure:
            return replace(self, outcome=outcome, phase=FeaturePhase.BLOCKED)
        if outcome.memory_update_required:
            return replace(self, outcome=outcome, phase=FeaturePhase.MEMORY_UPDATE)
        return replace(self, outcome=outcome, phase=FeaturePhase.AWAITING_FINAL_APPROVAL)

    def confirm_memory_update(self) -> FeatureRun:
        if self.phase is not FeaturePhase.MEMORY_UPDATE:
            raise FeatureFlowError("No memory update is awaiting confirmation")
        return replace(
            self,
            memory_update_confirmed=True,
            phase=FeaturePhase.AWAITING_FINAL_APPROVAL,
        )

    def approve_final(self) -> FeatureRun:
        if self.phase is not FeaturePhase.AWAITING_FINAL_APPROVAL:
            raise FeatureFlowError("Feature is not awaiting final approval")
        return replace(self, final_approved=True, phase=FeaturePhase.COMPLETED)

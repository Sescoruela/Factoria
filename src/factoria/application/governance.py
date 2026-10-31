from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable

from factoria.domain.permissions import PermissionProfile


class PolicyLevel(StrEnum):
    ORGANIZATION = "organization"
    PROJECT = "project"
    USER = "user"
    COMMAND = "command"


class GovernedAction(StrEnum):
    READ = "read"
    WRITE = "write"
    COMMAND = "command"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True, slots=True)
class PolicyRule:
    level: PolicyLevel
    action: GovernedAction
    allowed: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    base_profile: PermissionProfile
    requested_profile: PermissionProfile | None = None
    flow_authorized: bool = False
    destructive_confirmed: bool = False
    rules: tuple[PolicyRule, ...] = field(default_factory=tuple)

    @property
    def effective_profile(self) -> PermissionProfile:
        return self.requested_profile or self.base_profile

    @property
    def escalated(self) -> bool:
        if self.requested_profile is None:
            return False
        order = {
            PermissionProfile.SAFE: 0,
            PermissionProfile.NORMAL: 1,
            PermissionProfile.POWER: 2,
        }
        return order[self.requested_profile] > order[self.base_profile]


@dataclass(frozen=True, slots=True)
class GovernanceDecision:
    allowed: bool
    requires_confirmation: bool = False
    reason: str | None = None
    effective_profile: PermissionProfile = PermissionProfile.NORMAL
    escalated: bool = False


class ExecutionGovernor:
    """Resolve layered policy without allowing lower levels to relax higher restrictions."""

    _precedence = {
        PolicyLevel.ORGANIZATION: 0,
        PolicyLevel.PROJECT: 1,
        PolicyLevel.USER: 2,
        PolicyLevel.COMMAND: 3,
    }

    def evaluate(self, action: GovernedAction, context: ExecutionContext) -> GovernanceDecision:
        matching = sorted(
            (rule for rule in context.rules if rule.action is action),
            key=lambda rule: self._precedence[rule.level],
        )
        for rule in matching:
            if not rule.allowed:
                return GovernanceDecision(
                    allowed=False,
                    reason=rule.reason or f"{rule.level.value} policy blocks {action.value}",
                    effective_profile=context.effective_profile,
                    escalated=context.escalated,
                )

        profile = context.effective_profile
        if action is not GovernedAction.DESTRUCTIVE:
            return GovernanceDecision(
                allowed=True,
                effective_profile=profile,
                escalated=context.escalated,
            )

        if profile is PermissionProfile.SAFE:
            return GovernanceDecision(
                allowed=False,
                reason="Destructive actions are forbidden in safe profile",
                effective_profile=profile,
                escalated=context.escalated,
            )
        if profile is PermissionProfile.NORMAL:
            if context.destructive_confirmed:
                return GovernanceDecision(
                    allowed=True,
                    effective_profile=profile,
                    escalated=context.escalated,
                )
            return GovernanceDecision(
                allowed=True,
                requires_confirmation=True,
                reason="Normal profile requires explicit confirmation for destructive actions",
                effective_profile=profile,
                escalated=context.escalated,
            )
        if context.flow_authorized:
            return GovernanceDecision(
                allowed=True,
                effective_profile=profile,
                escalated=context.escalated,
            )
        if context.destructive_confirmed:
            return GovernanceDecision(
                allowed=True,
                effective_profile=profile,
                escalated=context.escalated,
            )
        return GovernanceDecision(
            allowed=True,
            requires_confirmation=True,
            reason="Power profile can skip confirmation only for an already authorized flow",
            effective_profile=profile,
            escalated=context.escalated,
        )

    def assert_allowed(self, action: GovernedAction, context: ExecutionContext) -> GovernanceDecision:
        decision = self.evaluate(action, context)
        if not decision.allowed:
            raise PermissionError(decision.reason or "Action blocked by execution policy")
        return decision

    def summarize_rules(self, rules: Iterable[PolicyRule]) -> tuple[str, ...]:
        return tuple(
            f"{rule.level.value}:{rule.action.value}:{'allow' if rule.allowed else 'block'}"
            for rule in rules
        )

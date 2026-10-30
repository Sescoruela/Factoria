from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PermissionProfile(StrEnum):
    SAFE = "safe"
    NORMAL = "normal"
    POWER = "power"


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    allowed: bool
    requires_confirmation: bool = False
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PermissionPolicy:
    profile: PermissionProfile

    def evaluate(self, *, destructive: bool, flow_authorized: bool = False) -> PermissionDecision:
        if not destructive:
            return PermissionDecision(allowed=True)

        if self.profile is PermissionProfile.SAFE:
            return PermissionDecision(
                allowed=False,
                reason="Destructive actions are forbidden in safe profile",
            )

        if self.profile is PermissionProfile.NORMAL:
            return PermissionDecision(allowed=True, requires_confirmation=True)

        if self.profile is PermissionProfile.POWER and flow_authorized:
            return PermissionDecision(allowed=True, requires_confirmation=False)

        return PermissionDecision(
            allowed=True,
            requires_confirmation=True,
            reason="Power profile requires an authorized flow to skip confirmation",
        )

import unittest

from factoria.application.governance import (
    ExecutionContext,
    ExecutionGovernor,
    GovernedAction,
    PolicyLevel,
    PolicyRule,
)
from factoria.domain.permissions import PermissionProfile


class ExecutionGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.governor = ExecutionGovernor()

    def test_safe_profile_blocks_destructive_action_even_when_confirmed(self) -> None:
        decision = self.governor.evaluate(
            GovernedAction.DESTRUCTIVE,
            ExecutionContext(
                base_profile=PermissionProfile.SAFE,
                destructive_confirmed=True,
                flow_authorized=True,
            ),
        )
        self.assertFalse(decision.allowed)
        self.assertFalse(decision.requires_confirmation)

    def test_normal_profile_requires_confirmation(self) -> None:
        pending = self.governor.evaluate(
            GovernedAction.DESTRUCTIVE,
            ExecutionContext(base_profile=PermissionProfile.NORMAL),
        )
        confirmed = self.governor.evaluate(
            GovernedAction.DESTRUCTIVE,
            ExecutionContext(
                base_profile=PermissionProfile.NORMAL,
                destructive_confirmed=True,
            ),
        )
        self.assertTrue(pending.allowed)
        self.assertTrue(pending.requires_confirmation)
        self.assertTrue(confirmed.allowed)
        self.assertFalse(confirmed.requires_confirmation)

    def test_power_skips_confirmation_only_for_authorized_flow(self) -> None:
        unauthorized = self.governor.evaluate(
            GovernedAction.DESTRUCTIVE,
            ExecutionContext(base_profile=PermissionProfile.POWER),
        )
        authorized = self.governor.evaluate(
            GovernedAction.DESTRUCTIVE,
            ExecutionContext(
                base_profile=PermissionProfile.POWER,
                flow_authorized=True,
            ),
        )
        self.assertTrue(unauthorized.requires_confirmation)
        self.assertFalse(authorized.requires_confirmation)

    def test_organization_block_cannot_be_relaxed_by_command_allow(self) -> None:
        decision = self.governor.evaluate(
            GovernedAction.DESTRUCTIVE,
            ExecutionContext(
                base_profile=PermissionProfile.POWER,
                requested_profile=PermissionProfile.POWER,
                flow_authorized=True,
                rules=(
                    PolicyRule(
                        PolicyLevel.ORGANIZATION,
                        GovernedAction.DESTRUCTIVE,
                        allowed=False,
                        reason="Organization forbids destructive actions",
                    ),
                    PolicyRule(
                        PolicyLevel.COMMAND,
                        GovernedAction.DESTRUCTIVE,
                        allowed=True,
                    ),
                ),
            ),
        )
        self.assertFalse(decision.allowed)
        self.assertIn("Organization", decision.reason or "")

    def test_temporary_escalation_is_detected(self) -> None:
        decision = self.governor.evaluate(
            GovernedAction.WRITE,
            ExecutionContext(
                base_profile=PermissionProfile.SAFE,
                requested_profile=PermissionProfile.NORMAL,
            ),
        )
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.escalated)
        self.assertEqual(decision.effective_profile, PermissionProfile.NORMAL)


if __name__ == "__main__":
    unittest.main()

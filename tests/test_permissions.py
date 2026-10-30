from __future__ import annotations

import unittest

from factoria.domain.permissions import PermissionPolicy, PermissionProfile


class PermissionPolicyTests(unittest.TestCase):
    def test_safe_forbids_destructive_actions(self) -> None:
        decision = PermissionPolicy(PermissionProfile.SAFE).evaluate(destructive=True)
        self.assertFalse(decision.allowed)

    def test_normal_requires_confirmation_for_destructive_actions(self) -> None:
        decision = PermissionPolicy(PermissionProfile.NORMAL).evaluate(destructive=True)
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.requires_confirmation)

    def test_power_skips_confirmation_only_for_authorized_flow(self) -> None:
        policy = PermissionPolicy(PermissionProfile.POWER)
        unauthorized = policy.evaluate(destructive=True, flow_authorized=False)
        authorized = policy.evaluate(destructive=True, flow_authorized=True)
        self.assertTrue(unauthorized.requires_confirmation)
        self.assertTrue(authorized.allowed)
        self.assertFalse(authorized.requires_confirmation)


if __name__ == "__main__":
    unittest.main()

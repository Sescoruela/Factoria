from factoria.domain.permissions import PermissionPolicy, PermissionProfile


def test_safe_forbids_destructive_actions() -> None:
    decision = PermissionPolicy(PermissionProfile.SAFE).evaluate(destructive=True)
    assert decision.allowed is False


def test_normal_requires_confirmation_for_destructive_actions() -> None:
    decision = PermissionPolicy(PermissionProfile.NORMAL).evaluate(destructive=True)
    assert decision.allowed is True
    assert decision.requires_confirmation is True


def test_power_skips_confirmation_only_for_authorized_flow() -> None:
    policy = PermissionPolicy(PermissionProfile.POWER)

    unauthorized = policy.evaluate(destructive=True, flow_authorized=False)
    authorized = policy.evaluate(destructive=True, flow_authorized=True)

    assert unauthorized.requires_confirmation is True
    assert authorized.allowed is True
    assert authorized.requires_confirmation is False

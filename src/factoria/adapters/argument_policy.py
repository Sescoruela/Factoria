from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


class ArgumentPolicyError(ValueError):
    """Raised when adapter arguments are not explicitly permitted by Factoria."""


@dataclass(frozen=True, slots=True)
class AdapterArgumentPolicy:
    """Allow-list policy for adapter arguments supplied outside the adapter itself.

    Keys are flag names. Values are the exact allowed values for value-taking flags.
    An empty tuple means the flag is a boolean switch and must not consume a value.
    Anything not declared here is denied.
    """

    allowed: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: MappingProxyType({}))
    reserved: frozenset[str] = frozenset()

    def validate(self, args: tuple[str, ...]) -> tuple[str, ...]:
        validated: list[str] = []
        index = 0
        while index < len(args):
            flag = args[index]
            if not flag.startswith("-"):
                raise ArgumentPolicyError(
                    f"Adapter argument policy rejects positional argument {flag!r}"
                )
            if flag in self.reserved:
                raise ArgumentPolicyError(
                    f"Adapter flag {flag!r} is controlled by Factoria and cannot be supplied through extra_args"
                )
            values = self.allowed.get(flag)
            if values is None:
                raise ArgumentPolicyError(f"Adapter flag {flag!r} is not explicitly allowed")
            validated.append(flag)
            if values:
                index += 1
                if index >= len(args):
                    raise ArgumentPolicyError(
                        f"Adapter flag {flag!r} requires an explicitly allowed value"
                    )
                value = args[index]
                if value not in values:
                    raise ArgumentPolicyError(
                        f"Adapter flag {flag!r} rejects value {value!r}; allowed values: {', '.join(values)}"
                    )
                validated.append(value)
            index += 1
        return tuple(validated)


DENY_ALL_ARGUMENTS = AdapterArgumentPolicy()

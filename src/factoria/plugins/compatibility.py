from __future__ import annotations

from dataclasses import dataclass
import re


_VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


@dataclass(frozen=True, order=True, slots=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = _VERSION_RE.fullmatch(value.strip())
        if match is None:
            raise ValueError(f"Invalid semantic version: {value}")
        return cls(*(int(part) for part in match.groups()))


def is_compatible(version: str, constraint: str) -> bool:
    current = Version.parse(version)
    clauses = [item.strip() for item in constraint.split(",") if item.strip()]
    if not clauses:
        raise ValueError("Compatibility constraint cannot be empty")

    for clause in clauses:
        operator = next(
            (
                candidate
                for candidate in (">=", "<=", "==", ">", "<")
                if clause.startswith(candidate)
            ),
            None,
        )
        if operator is None:
            raise ValueError(f"Unsupported compatibility clause: {clause}")
        expected = Version.parse(clause[len(operator) :].strip())
        if operator == ">=" and not current >= expected:
            return False
        if operator == "<=" and not current <= expected:
            return False
        if operator == "==" and not current == expected:
            return False
        if operator == ">" and not current > expected:
            return False
        if operator == "<" and not current < expected:
            return False
    return True

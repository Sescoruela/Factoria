from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


class VersionError(ValueError):
    """Raised when a version is not valid SemVer."""


@total_ordering
@dataclass(frozen=True, slots=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    build: str | None = None

    @classmethod
    def parse(cls, value: str) -> "SemVer":
        match = _SEMVER_RE.fullmatch(value.strip())
        if match is None:
            raise VersionError(f"Invalid semantic version: {value!r}")
        prerelease = (
            tuple(match.group("prerelease").split(".")) if match.group("prerelease") else ()
        )
        for item in prerelease:
            if item.isdigit() and len(item) > 1 and item.startswith("0"):
                raise VersionError(f"Invalid numeric prerelease identifier: {item!r}")
        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            prerelease=prerelease,
            build=match.group("build"),
        )

    def __str__(self) -> str:
        value = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            value += "-" + ".".join(self.prerelease)
        if self.build:
            value += "+" + self.build
        return value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._precedence_key() == other._precedence_key()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        core_self = (self.major, self.minor, self.patch)
        core_other = (other.major, other.minor, other.patch)
        if core_self != core_other:
            return core_self < core_other
        return _compare_prerelease(self.prerelease, other.prerelease) < 0

    def _precedence_key(self) -> tuple[int, int, int, tuple[str, ...]]:
        return (self.major, self.minor, self.patch, self.prerelease)

    def is_major_upgrade_from(self, other: "SemVer") -> bool:
        return self > other and self.major > other.major


def _compare_prerelease(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    if left == right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    for l_item, r_item in zip(left, right):
        if l_item == r_item:
            continue
        l_num = l_item.isdigit()
        r_num = r_item.isdigit()
        if l_num and r_num:
            return -1 if int(l_item) < int(r_item) else 1
        if l_num != r_num:
            return -1 if l_num else 1
        return -1 if l_item < r_item else 1
    return -1 if len(left) < len(right) else 1

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from factoria.versioning import SemVer


class PackageVersionError(RuntimeError):
    """Raised when Factoria's installed package version cannot be determined."""


def installed_version_text() -> str:
    """Return the canonical installed Factoria version from package metadata."""
    try:
        return version("factoria")
    except PackageNotFoundError as exc:
        raise PackageVersionError(
            "Factoria package metadata is unavailable; install the package before running the CLI"
        ) from exc


def installed_semver() -> SemVer:
    return SemVer.parse(installed_version_text())

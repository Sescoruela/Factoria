from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from factoria.versioning import SemVer

_MANAGED_CONFIG_MARKER = "# factoria: managed global config"


class UpdateError(RuntimeError):
    """Raised when Factoria cannot update or roll back safely."""


@dataclass(frozen=True, slots=True)
class ReleaseMetadata:
    version: SemVer
    notes: tuple[str, ...] = ()
    memory_changes: tuple[str, ...] = ()
    config_changes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UpdatePlan:
    source_root: Path
    remote: str
    branch: str
    remote_url: str
    current_version: SemVer
    target_version: SemVer
    current_sha: str
    target_sha: str
    changes: tuple[str, ...]
    release: ReleaseMetadata | None = None

    @property
    def available(self) -> bool:
        return self.target_version > self.current_version

    @property
    def major_update(self) -> bool:
        return self.target_version.is_major_upgrade_from(self.current_version)


@dataclass(frozen=True, slots=True)
class UpdateResult:
    version: SemVer
    commit_sha: str
    health_ok: bool
    health_details: str


@dataclass(frozen=True, slots=True)
class RollbackState:
    previous_version: str
    previous_sha: str
    target_version: str
    target_sha: str
    remote_url: str
    config_backup: str | None
    created_at: str


@dataclass(slots=True)
class UpdateService:
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
    python_executable: str = sys.executable

    def discover_source_root(self, explicit: Path | None = None) -> Path:
        if explicit is not None:
            root = explicit.expanduser().resolve()
            if not (root / ".git").exists() or not (root / "pyproject.toml").exists():
                raise UpdateError(f"Not a Factoria Git checkout: {root}")
            return root

        start = Path(__file__).resolve()
        for candidate in (start, *start.parents):
            if candidate.is_dir() and (candidate / ".git").exists() and (candidate / "pyproject.toml").exists():
                return candidate
        raise UpdateError(
            "No Factoria Git checkout found. Re-run with `factoria update --source <clone>`"
        )

    def inspect(
        self,
        source_root: Path,
        *,
        remote: str,
        branch: str,
        current_version: SemVer,
    ) -> UpdatePlan:
        root = self.discover_source_root(source_root)
        self._run_git(root, "fetch", "--quiet", "--no-tags", remote, branch)
        target_sha = self._run_git(root, "rev-parse", "FETCH_HEAD").stdout.strip()
        current_sha = self._run_git(root, "rev-parse", "HEAD").stdout.strip()
        remote_url = self._run_git(root, "remote", "get-url", remote).stdout.strip()
        pyproject = self._run_git(root, "show", "FETCH_HEAD:pyproject.toml").stdout
        target_version = _project_version(pyproject)
        log = self._run_git(
            root,
            "log",
            "--format=%h %s",
            "--max-count=20",
            f"{current_sha}..{target_sha}",
            check=False,
        ).stdout
        changes = tuple(line.strip() for line in log.splitlines() if line.strip())
        release = self._read_release(root)
        if release is not None and release.version != target_version:
            raise UpdateError(
                f"Release metadata version {release.version} does not match target {target_version}"
            )
        return UpdatePlan(
            source_root=root,
            remote=remote,
            branch=branch,
            remote_url=remote_url,
            current_version=current_version,
            target_version=target_version,
            current_sha=current_sha,
            target_sha=target_sha,
            changes=changes,
            release=release,
        )

    def apply(
        self,
        plan: UpdatePlan,
        *,
        state_path: Path,
        config_path: Path,
        confirmed: bool,
    ) -> UpdateResult:
        if not confirmed:
            raise UpdateError("Explicit confirmation is required before updating Factoria")
        if not plan.available:
            raise UpdateError("No newer semantic version is available")

        state = RollbackState(
            previous_version=str(plan.current_version),
            previous_sha=plan.current_sha,
            target_version=str(plan.target_version),
            target_sha=plan.target_sha,
            remote_url=plan.remote_url,
            config_backup=_managed_config_backup(config_path),
            created_at=datetime.now(UTC).isoformat(),
        )
        _write_state(state_path, state)
        self._install(plan.remote_url, plan.target_sha)
        health_ok, details = self.health_check()
        return UpdateResult(
            version=plan.target_version,
            commit_sha=plan.target_sha,
            health_ok=health_ok,
            health_details=details,
        )

    def rollback(
        self,
        *,
        state_path: Path,
        config_path: Path,
        confirmed: bool,
    ) -> UpdateResult:
        if not confirmed:
            raise UpdateError("Explicit confirmation is required before rolling back Factoria")
        state = _read_state(state_path)
        self._install(state.remote_url, state.previous_sha)
        if state.config_backup is not None:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(state.config_backup, encoding="utf-8", newline="")
        health_ok, details = self.health_check()
        if health_ok:
            state_path.unlink(missing_ok=True)
        return UpdateResult(
            version=SemVer.parse(state.previous_version),
            commit_sha=state.previous_sha,
            health_ok=health_ok,
            health_details=details,
        )

    def health_check(self) -> tuple[bool, str]:
        command = [
            self.python_executable,
            "-c",
            "from factoria.entrypoint import build_update_parser; build_update_parser()",
        ]
        completed = self.runner(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
        details = (completed.stdout or completed.stderr).strip() or f"exit={completed.returncode}"
        return completed.returncode == 0, details

    def _install(self, remote_url: str, sha: str) -> None:
        spec = _git_requirement(remote_url, sha)
        completed = self.runner(
            [self.python_executable, "-m", "pip", "install", "--upgrade", spec],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=600,
        )
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout).strip()
            raise UpdateError(f"Factoria installation failed: {details[-2000:]}")

    def _read_release(self, root: Path) -> ReleaseMetadata | None:
        completed = self._run_git(
            root,
            "show",
            "FETCH_HEAD:src/factoria/release.toml",
            check=False,
        )
        if completed.returncode != 0:
            return None
        return _release_metadata(completed.stdout)

    def _run_git(self, root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        completed = self.runner(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=120,
        )
        if check and completed.returncode != 0:
            details = (completed.stderr or completed.stdout).strip()
            raise UpdateError(f"Git command failed: {details}")
        return completed


def _project_version(content: str) -> SemVer:
    data = tomllib.loads(content)
    project = data.get("project", {})
    if not isinstance(project, dict) or not isinstance(project.get("version"), str):
        raise UpdateError("Target pyproject.toml does not define project.version")
    return SemVer.parse(project["version"])


def _release_metadata(content: str) -> ReleaseMetadata:
    data = tomllib.loads(content)
    version = data.get("version")
    if not isinstance(version, str):
        raise UpdateError("release.toml must define a string version")
    return ReleaseMetadata(
        version=SemVer.parse(version),
        notes=_string_tuple(data.get("notes"), "notes"),
        memory_changes=_string_tuple(data.get("memory_changes"), "memory_changes"),
        config_changes=_string_tuple(data.get("config_changes"), "config_changes"),
    )


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise UpdateError(f"release.toml {field_name} must be a list of strings")
    return tuple(value)


def _managed_config_backup(path: Path) -> str | None:
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8", errors="replace")
    if _MANAGED_CONFIG_MARKER not in content.splitlines()[:3]:
        return None
    return content


def _write_state(path: Path, state: RollbackState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_state(path: Path) -> RollbackState:
    if not path.exists():
        raise UpdateError("No previous Factoria version is available for rollback")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return RollbackState(**data)
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        raise UpdateError("Rollback state is invalid") from exc


def _git_requirement(remote_url: str, sha: str) -> str:
    url = remote_url.strip()
    if url.startswith("git@") and ":" in url:
        host, path = url.split(":", 1)
        url = f"ssh://{host}/{path}"
    elif url.startswith("/"):
        url = Path(url).resolve().as_uri()
    if not url.startswith(("http://", "https://", "ssh://", "file://", "git://")):
        raise UpdateError(f"Unsupported Git remote URL: {remote_url!r}")
    return f"git+{url}@{sha}"

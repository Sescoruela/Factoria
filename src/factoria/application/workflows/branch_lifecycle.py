from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class BranchLifecycleError(RuntimeError):
    """Raised when branch lifecycle operations cannot be performed safely."""


@dataclass(frozen=True, slots=True)
class UniqueCommit:
    sha: str
    subject: str


@dataclass(frozen=True, slots=True)
class BranchInspection:
    branch: str
    current_branch: str
    head_sha: str | None
    worktree_changes: tuple[str, ...]
    unique_commits: tuple[UniqueCommit, ...]

    @property
    def has_worktree_changes(self) -> bool:
        return bool(self.worktree_changes)


@dataclass(frozen=True, slots=True)
class GitBranchLifecycle:
    project_root: Path
    base_branch: str = "main"

    def inspect(self, branch: str) -> BranchInspection:
        if not self.branch_exists(branch):
            raise BranchLifecycleError(f"Branch does not exist: {branch}")
        current = self._git("branch", "--show-current").strip()
        head = self._git("rev-parse", branch).strip() or None
        changes = tuple(
            line for line in self._git("status", "--porcelain").splitlines() if line.strip()
        )
        unique = self.unique_commits(branch)
        return BranchInspection(
            branch=branch,
            current_branch=current,
            head_sha=head,
            worktree_changes=changes,
            unique_commits=unique,
        )

    def branch_exists(self, branch: str) -> bool:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(self.project_root),
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}",
            ],
            check=False,
            capture_output=True,
        )
        return result.returncode == 0

    def unique_commits(self, branch: str) -> tuple[UniqueCommit, ...]:
        if not self.branch_exists(self.base_branch):
            return ()
        output = self._git(
            "log",
            f"{self.base_branch}..{branch}",
            "--format=%H%x09%s",
        )
        commits: list[UniqueCommit] = []
        for line in output.splitlines():
            if not line.strip():
                continue
            sha, _, subject = line.partition("\t")
            commits.append(UniqueCommit(sha=sha, subject=subject))
        return tuple(commits)

    def switch_to_flow_branch(self, branch: str) -> None:
        if self._git("status", "--porcelain").strip():
            raise BranchLifecycleError(
                "Cannot switch branches while the working tree has pending changes"
            )
        if not self.branch_exists(branch):
            raise BranchLifecycleError(f"Flow branch no longer exists: {branch}")
        self._git("switch", branch)

    def backup_branch(self, branch: str, backup_name: str) -> None:
        if self.branch_exists(backup_name):
            raise BranchLifecycleError(f"Backup branch already exists: {backup_name}")
        self._git("branch", backup_name, branch)

    def delete_branch(self, branch: str, *, backup_name: str | None = None) -> str | None:
        inspection = self.inspect(branch)
        if inspection.has_worktree_changes:
            raise BranchLifecycleError(
                "Cannot delete a flow branch while the working tree has pending changes"
            )
        if inspection.unique_commits and backup_name is None:
            raise BranchLifecycleError(
                "Branch has unique commits; create an explicit backup branch before deletion"
            )
        if backup_name is not None:
            self.backup_branch(branch, backup_name)

        if inspection.current_branch == branch:
            if not self.branch_exists(self.base_branch):
                raise BranchLifecycleError(
                    f"Cannot leave {branch!r}: base branch {self.base_branch!r} does not exist"
                )
            self._git("switch", self.base_branch)

        flag = "-D" if inspection.unique_commits else "-d"
        self._git("branch", flag, branch)
        return backup_name

    def _git(self, *args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(self.project_root), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return completed.stdout

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from factoria.security import SecretBlockedError, SecretIncidentStore, SecretScanner

from .flow_service import FlowExecution


class GitLifecycleError(RuntimeError):
    """Raised when Factoria cannot safely prepare or create a commit."""


@dataclass(frozen=True, slots=True)
class GitChange:
    status: str
    path: str


@dataclass(frozen=True, slots=True)
class CommitProposal:
    flow_id: str
    branch: str
    changes: tuple[GitChange, ...]
    message: str


@dataclass(frozen=True, slots=True)
class CommitResult:
    sha: str
    message: str
    files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GitLifecycle:
    project_root: Path
    secret_scanner: SecretScanner = SecretScanner()

    def _assert_no_open_incidents(self) -> None:
        incidents = SecretIncidentStore(self.project_root).open()
        if incidents:
            labels = ", ".join(
                f"{item.incident_id[:8]}:{item.secret_type}@{item.location}" for item in incidents
            )
            raise GitLifecycleError(
                "Open secret incident(s) block commit until rotation/revocation is confirmed and absence is verified: "
                + labels
            )

    def _scan_and_persist(self, paths: tuple[str, ...]) -> None:
        findings = self.secret_scanner.scan_files(self.project_root, paths)
        if findings:
            SecretIncidentStore(self.project_root).record(findings)
            raise SecretBlockedError(findings)

    def prepare(self, execution: FlowExecution, *, message: str | None = None) -> CommitProposal:
        self._assert_no_open_incidents()
        branch = self._git("branch", "--show-current").strip()
        if not branch:
            raise GitLifecycleError("Detached HEAD is not supported")
        if branch == "main":
            raise GitLifecycleError("Factoria never commits flow changes directly on main")
        changes = self.changes()
        if not changes:
            raise GitLifecycleError("No pending changes to commit")
        self._scan_and_persist(tuple(item.path for item in changes))
        proposed = message or self._default_message(execution)
        if not proposed.strip():
            raise GitLifecycleError("Commit message cannot be empty")
        return CommitProposal(
            flow_id=execution.flow.flow_id,
            branch=branch,
            changes=changes,
            message=proposed.strip(),
        )

    def changes(self) -> tuple[GitChange, ...]:
        output = self._git("status", "--porcelain=v1")
        changes: list[GitChange] = []
        for raw in output.splitlines():
            if len(raw) < 4:
                continue
            status = raw[:2]
            path = raw[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            changes.append(GitChange(status=status, path=path.strip('"')))
        return tuple(changes)

    def commit(
        self,
        proposal: CommitProposal,
        *,
        confirmed: bool,
        message: str | None = None,
    ) -> CommitResult:
        if not confirmed:
            raise GitLifecycleError("Explicit confirmation is required before committing")
        self._assert_no_open_incidents()
        current_branch = self._git("branch", "--show-current").strip()
        if current_branch != proposal.branch:
            raise GitLifecycleError(
                f"Branch changed since preview: expected {proposal.branch!r}, got {current_branch!r}"
            )
        current_changes = self.changes()
        if current_changes != proposal.changes:
            raise GitLifecycleError(
                "Working tree changed after the commit preview; generate a new preview before committing"
            )
        self._scan_and_persist(tuple(item.path for item in current_changes))
        final_message = (message or proposal.message).strip()
        if not final_message:
            raise GitLifecycleError("Commit message cannot be empty")

        files = tuple(item.path for item in proposal.changes)
        self._git("add", "--", *files)
        self._git("commit", "-m", final_message)
        if self.changes():
            raise GitLifecycleError(
                "Commit was created but the working tree is not clean; inspect remaining changes before closing the flow"
            )
        sha = self._git("rev-parse", "HEAD").strip()
        return CommitResult(sha=sha, message=final_message, files=files)

    def current_branch(self) -> str:
        return self._git("branch", "--show-current").strip()

    def head_sha(self) -> str:
        return self._git("rev-parse", "HEAD").strip()

    def _default_message(self, execution: FlowExecution) -> str:
        prefix = "fix" if execution.flow.kind == "fix" else "feat"
        subject = (execution.label or execution.flow.flow_id).strip()
        subject = " ".join(subject.split())
        return f"{prefix}: {subject}"

    def _git(self, *args: str) -> str:
        try:
            completed = subprocess.run(
                ["git", "-C", str(self.project_root), *args],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or str(exc)).strip()
            raise GitLifecycleError(details) from exc
        return completed.stdout

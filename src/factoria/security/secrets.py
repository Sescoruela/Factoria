from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Iterable


class SecretType(StrEnum):
    PRIVATE_KEY = "private_key"
    BEARER_TOKEN = "bearer_token"
    CREDENTIAL_ASSIGNMENT = "credential_assignment"
    PROVIDER_TOKEN = "provider_token"


class SecretSource(StrEnum):
    FILE = "file"
    OUTPUT = "output"


@dataclass(frozen=True, slots=True)
class SecretFinding:
    secret_type: SecretType
    source: SecretSource
    location: str
    fingerprint: str
    preview: str = "[REDACTED]"
    _raw_value: str = field(default="", repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class SecretIncident:
    findings: tuple[SecretFinding, ...]
    rotation_confirmed: bool = False

    @property
    def blocked(self) -> bool:
        return bool(self.findings)

    def confirm_rotation(self) -> SecretIncident:
        return SecretIncident(findings=self.findings, rotation_confirmed=True)


class SecretBlockedError(RuntimeError):
    def __init__(self, findings: tuple[SecretFinding, ...]) -> None:
        self.findings = findings
        labels = ", ".join(f"{item.secret_type.value}@{item.location}" for item in findings)
        super().__init__(f"Potential secret detected; flow blocked: {labels}")


@dataclass(frozen=True, slots=True)
class SecretScanner:
    max_file_bytes: int = 1_000_000

    _patterns = (
        (SecretType.PRIVATE_KEY, re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
        (SecretType.BEARER_TOKEN, re.compile(r"(?i)\bbearer\s+([A-Za-z0-9._~+/-]{20,})")),
        (SecretType.PROVIDER_TOKEN, re.compile(r"\b(?:ghp|github_pat|sk)-[A-Za-z0-9_-]{20,}\b")),
        (
            SecretType.CREDENTIAL_ASSIGNMENT,
            re.compile(
                r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|client[_-]?secret)\b\s*[:=]\s*[\"']([^\"'\s]{12,})[\"']"
            ),
        ),
    )

    def scan_text(self, text: str, *, location: str, source: SecretSource = SecretSource.OUTPUT) -> tuple[SecretFinding, ...]:
        findings: list[SecretFinding] = []
        for secret_type, pattern in self._patterns:
            for match in pattern.finditer(text):
                raw = match.group(1) if match.lastindex else match.group(0)
                findings.append(self._finding(secret_type, source, location, raw))
        return self._dedupe(findings)

    def scan_files(self, project_root: Path, paths: Iterable[str]) -> tuple[SecretFinding, ...]:
        root = project_root.resolve()
        findings: list[SecretFinding] = []
        for relative in paths:
            path = (root / relative).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                continue
            if not path.is_file():
                continue
            try:
                if path.stat().st_size > self.max_file_bytes:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            findings.extend(self.scan_text(text, location=relative, source=SecretSource.FILE))
        return self._dedupe(findings)

    def verify_removed(self, project_root: Path, incident: SecretIncident) -> bool:
        if not incident.rotation_confirmed:
            return False
        root = project_root.resolve()
        for finding in incident.findings:
            if finding.source is not SecretSource.FILE:
                continue
            path = (root / finding.location).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                return False
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if finding._raw_value and finding._raw_value in text:
                return False
        return True

    def redact(self, text: str) -> tuple[str, tuple[SecretFinding, ...]]:
        findings = self.scan_text(text, location="captured-output", source=SecretSource.OUTPUT)
        sanitized = text
        for finding in findings:
            if finding._raw_value:
                sanitized = sanitized.replace(finding._raw_value, "[REDACTED]")
        return sanitized, findings

    @staticmethod
    def changed_paths(project_root: Path) -> tuple[str, ...]:
        completed = subprocess.run(
            ["git", "-C", str(project_root), "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            check=True,
            capture_output=True,
        )
        raw = completed.stdout.decode("utf-8", errors="replace")
        parts = [item for item in raw.split("\0") if item]
        paths: list[str] = []
        index = 0
        while index < len(parts):
            entry = parts[index]
            path = entry[3:] if len(entry) >= 4 else ""
            status = entry[:2]
            if any(flag in status for flag in ('R', 'C')) and index + 1 < len(parts):
                index += 1
            if path:
                paths.append(path)
            index += 1
        return tuple(paths)

    @staticmethod
    def _finding(secret_type: SecretType, source: SecretSource, location: str, raw: str) -> SecretFinding:
        fingerprint = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]
        return SecretFinding(
            secret_type=secret_type,
            source=source,
            location=location,
            fingerprint=fingerprint,
            _raw_value=raw,
        )

    @staticmethod
    def _dedupe(findings: Iterable[SecretFinding]) -> tuple[SecretFinding, ...]:
        unique: dict[tuple[str, str, str, str], SecretFinding] = {}
        for finding in findings:
            key = (
                finding.secret_type.value,
                finding.source.value,
                finding.location,
                finding.fingerprint,
            )
            unique[key] = finding
        return tuple(unique.values())

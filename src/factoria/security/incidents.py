from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from .secrets import SecretFinding, SecretScanner, SecretSource


class IncidentStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


@dataclass(frozen=True, slots=True)
class SecretIncidentRecord:
    incident_id: str
    secret_type: str
    source: str
    location: str
    fingerprint: str
    status: IncidentStatus
    detected_at: str
    rotation_confirmed_at: str | None = None
    resolved_at: str | None = None


@dataclass(slots=True)
class SecretIncidentStore:
    project_root: Path

    @property
    def path(self) -> Path:
        return self.project_root / ".factoria" / "security" / "incidents.json"

    def list(self) -> tuple[SecretIncidentRecord, ...]:
        if not self.path.exists():
            return ()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return tuple(
                SecretIncidentRecord(
                    incident_id=item["incident_id"],
                    secret_type=item["secret_type"],
                    source=item["source"],
                    location=item["location"],
                    fingerprint=item["fingerprint"],
                    status=IncidentStatus(item["status"]),
                    detected_at=item["detected_at"],
                    rotation_confirmed_at=item.get("rotation_confirmed_at"),
                    resolved_at=item.get("resolved_at"),
                )
                for item in raw
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Secret incident store is invalid") from exc

    def open(self) -> tuple[SecretIncidentRecord, ...]:
        return tuple(item for item in self.list() if item.status is IncidentStatus.OPEN)

    def record(self, findings: Iterable[SecretFinding]) -> tuple[SecretIncidentRecord, ...]:
        records = list(self.list())
        now = datetime.now(UTC).isoformat()
        created: list[SecretIncidentRecord] = []
        existing = {
            (item.secret_type, item.source, item.location, item.fingerprint): item
            for item in records
            if item.status is IncidentStatus.OPEN
        }
        for finding in findings:
            key = (
                finding.secret_type.value,
                finding.source.value,
                finding.location,
                finding.fingerprint,
            )
            if key in existing:
                continue
            item = SecretIncidentRecord(
                incident_id=str(uuid.uuid4()),
                secret_type=finding.secret_type.value,
                source=finding.source.value,
                location=finding.location,
                fingerprint=finding.fingerprint,
                status=IncidentStatus.OPEN,
                detected_at=now,
            )
            records.append(item)
            existing[key] = item
            created.append(item)
        if created:
            self._write(records)
        return tuple(created)

    def confirm_rotation_and_resolve(
        self, incident_id: str, scanner: SecretScanner
    ) -> SecretIncidentRecord:
        records = list(self.list())
        index = next((i for i, item in enumerate(records) if item.incident_id == incident_id), None)
        if index is None:
            raise RuntimeError(f"Secret incident not found: {incident_id}")
        current = records[index]
        if current.status is IncidentStatus.RESOLVED:
            return current
        now = datetime.now(UTC).isoformat()
        confirmed = replace(current, rotation_confirmed_at=now)
        records[index] = confirmed
        self._write(records)
        if self._fingerprint_present(confirmed, scanner):
            raise RuntimeError(
                "Secret material is still detectable; incident remains open after rotation confirmation"
            )
        resolved = replace(confirmed, status=IncidentStatus.RESOLVED, resolved_at=now)
        records[index] = resolved
        self._write(records)
        return resolved

    def _fingerprint_present(self, incident: SecretIncidentRecord, scanner: SecretScanner) -> bool:
        root = self.project_root.resolve()
        if incident.source == SecretSource.FILE.value:
            path = (root / incident.location).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                return True
            if not path.is_file():
                return False
            findings = scanner.scan_files(root, (incident.location,))
            return any(item.fingerprint == incident.fingerprint for item in findings)

        candidates: list[str] = list(scanner.changed_paths(root))
        work = root / ".factoria" / "work"
        if work.exists():
            for path in work.rglob("*"):
                if path.is_file() and path.stat().st_size <= scanner.max_file_bytes:
                    try:
                        candidates.append(path.relative_to(root).as_posix())
                    except ValueError:
                        continue
        findings = scanner.scan_files(root, candidates)
        return any(item.fingerprint == incident.fingerprint for item in findings)

    def _write(self, records: Iterable[SecretIncidentRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = []
        for item in records:
            data = asdict(item)
            data["status"] = item.status.value
            payload.append(data)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

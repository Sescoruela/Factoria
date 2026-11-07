from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from factoria.domain.models import MemoryDocumentKind


DEFAULT_THRESHOLDS: Mapping[MemoryDocumentKind, int] = MappingProxyType(
    {
        MemoryDocumentKind.ARCHITECTURE: 25,
        MemoryDocumentKind.FLOWS: 15,
        MemoryDocumentKind.DECISIONS: 50,
        MemoryDocumentKind.TESTING: 20,
    }
)


@dataclass(frozen=True, slots=True)
class MemoryStalenessPolicy:
    thresholds: Mapping[MemoryDocumentKind, int] = field(default_factory=lambda: DEFAULT_THRESHOLDS)

    def threshold_for(self, document: MemoryDocumentKind) -> int:
        value = self.thresholds.get(document)
        if value is None or value < 1:
            raise ValueError(f"Missing positive staleness threshold for {document.value}")
        return value

    def is_stale(self, document: MemoryDocumentKind, commits_since_review: int) -> bool:
        if commits_since_review < 0:
            raise ValueError("commits_since_review cannot be negative")
        return commits_since_review >= self.threshold_for(document)

    def stale_documents(
        self,
        commits_since_review: Mapping[MemoryDocumentKind, int],
    ) -> tuple[MemoryDocumentKind, ...]:
        return tuple(
            document
            for document, count in commits_since_review.items()
            if self.is_stale(document, count)
        )

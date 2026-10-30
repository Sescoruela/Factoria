from __future__ import annotations

from typing import Protocol, Sequence

from .models import CheckResult, PluginManifest, ProjectMemory


class Adapter(Protocol):
    @property
    def name(self) -> str: ...

    def capabilities(self) -> frozenset[str]: ...

    def self_test(self) -> Sequence[CheckResult]: ...


class Plugin(Protocol):
    @property
    def manifest(self) -> PluginManifest: ...

    def register(self) -> None: ...


class MemoryStore(Protocol):
    def load(self, project_id: str) -> ProjectMemory: ...

    def save(self, project_id: str, memory: ProjectMemory) -> None: ...


class CheckRunner(Protocol):
    def run(self, category: str, scope: str | None = None) -> Sequence[CheckResult]: ...

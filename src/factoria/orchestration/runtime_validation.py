from __future__ import annotations

from dataclasses import dataclass, field

from factoria.adapters.base import ToolAdapter, ToolCapability


@dataclass(slots=True)
class AdapterRuntimeValidator:
    """Validate real adapter readiness once per process and cache the result."""

    _cache: dict[str, tuple[bool, frozenset[ToolCapability], tuple[str, ...]]] = field(
        default_factory=dict
    )

    def inspect(
        self, adapter: ToolAdapter
    ) -> tuple[bool, frozenset[ToolCapability], tuple[str, ...]]:
        cached = self._cache.get(adapter.name)
        if cached is not None:
            return cached

        if not adapter.available():
            result = (False, frozenset(), (f"Executable not available: {adapter.executable}",))
            self._cache[adapter.name] = result
            return result

        checks = tuple(adapter.self_test())
        failed = tuple(check.name for check in checks if check.required and not check.passed)
        ready = not failed
        capabilities = adapter.capabilities() if ready else frozenset()
        result = (ready, capabilities, failed)
        self._cache[adapter.name] = result
        return result

    def supports(self, adapter: ToolAdapter, required: frozenset[ToolCapability]) -> bool:
        ready, capabilities, _ = self.inspect(adapter)
        return ready and required.issubset(capabilities)

    def clear(self) -> None:
        self._cache.clear()

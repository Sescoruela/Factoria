from __future__ import annotations

from dataclasses import dataclass, field

from .base import ToolAdapter, ToolCapability


class AdapterSelectionError(RuntimeError):
    """Raised when no configured adapter can satisfy a request."""


@dataclass
class AdapterRegistry:
    adapters: dict[str, ToolAdapter] = field(default_factory=dict)

    def register(self, adapter: ToolAdapter) -> None:
        self.adapters[adapter.name] = adapter

    def get(self, name: str) -> ToolAdapter:
        try:
            return self.adapters[name]
        except KeyError as exc:
            raise AdapterSelectionError(f"Unknown adapter: {name}") from exc

    def available(self) -> tuple[ToolAdapter, ...]:
        return tuple(adapter for adapter in self.adapters.values() if adapter.available())

    def select(
        self,
        *,
        preferred: str | None = None,
        required_capabilities: frozenset[ToolCapability] = frozenset(),
    ) -> ToolAdapter:
        candidates: list[ToolAdapter] = []
        if preferred is not None:
            preferred_adapter = self.get(preferred)
            candidates.append(preferred_adapter)
        candidates.extend(
            adapter
            for adapter in self.adapters.values()
            if preferred is None or adapter.name != preferred
        )

        for adapter in candidates:
            if not adapter.available():
                continue
            if not required_capabilities.issubset(adapter.capabilities()):
                continue
            return adapter

        requested = ", ".join(sorted(cap.value for cap in required_capabilities)) or "none"
        preferred_text = preferred or "none"
        raise AdapterSelectionError(
            f"No available adapter satisfies capabilities [{requested}] "
            f"with preferred={preferred_text}"
        )

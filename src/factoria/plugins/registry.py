from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from pathlib import Path

from factoria.domain.models import PluginManifest


class PluginConflictError(RuntimeError):
    """Raised when two plugins with the same priority register the same name."""


class PluginSource(IntEnum):
    BUILTIN = 0
    ORGANIZATION = 1
    PERSONAL = 2


class PluginState(StrEnum):
    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PluginRecord:
    manifest: PluginManifest
    path: Path
    source: PluginSource
    state: PluginState = PluginState.VALID
    warnings: tuple[str, ...] = field(default_factory=tuple)


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, PluginRecord] = {}

    @property
    def plugins(self) -> tuple[PluginRecord, ...]:
        return tuple(sorted(self._plugins.values(), key=lambda record: record.manifest.name))

    def register(self, record: PluginRecord) -> None:
        existing = self._plugins.get(record.manifest.name)
        if existing is None:
            self._plugins[record.manifest.name] = record
            return

        if existing.source == record.source:
            raise PluginConflictError(
                f"Plugin '{record.manifest.name}' is defined more than once at priority "
                f"{record.source.name.lower()}"
            )

        if record.source > existing.source:
            self._plugins[record.manifest.name] = record

    def discover(self, roots: list[tuple[PluginSource, Path]]) -> tuple[PluginRecord, ...]:
        for source, root in roots:
            if not root.exists():
                continue
            for candidate in sorted(path for path in root.iterdir() if path.is_dir()):
                manifest_path = candidate / "plugin.toml"
                if not manifest_path.exists():
                    continue
                self.register(self._read_manifest(manifest_path, source))
        return self.plugins

    def _read_manifest(self, path: Path, source: PluginSource) -> PluginRecord:
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)

            required = ("name", "version", "type", "description")
            missing = tuple(key for key in required if not isinstance(data.get(key), str) or not data[key])
            if missing:
                raise ValueError(f"Missing required fields: {', '.join(missing)}")

            capabilities = data.get("capabilities", [])
            if not isinstance(capabilities, list) or not all(
                isinstance(item, str) for item in capabilities
            ):
                raise ValueError("capabilities must be a list of strings")

            compatibility = data.get("compatibility", {})
            if compatibility is None:
                compatibility = {}
            if not isinstance(compatibility, dict):
                raise ValueError("[compatibility] must be a TOML table")
            factoria = compatibility.get("factoria", ">=0.1.0")
            if not isinstance(factoria, str):
                raise ValueError("compatibility.factoria must be a string")

            manifest = PluginManifest(
                name=data["name"],
                version=data["version"],
                plugin_type=data["type"],
                description=data["description"],
                capabilities=tuple(capabilities),
                factoria_compatibility=factoria,
            )
            warnings: list[str] = []
            entrypoint = data.get("entrypoint")
            if entrypoint is not None and not isinstance(entrypoint, str):
                warnings.append("entrypoint is ignored because it is not a string")

            return PluginRecord(
                manifest=manifest,
                path=path.parent,
                source=source,
                state=PluginState.WARNING if warnings else PluginState.VALID,
                warnings=tuple(warnings),
            )
        except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
            fallback = PluginManifest(
                name=path.parent.name,
                version="0.0.0",
                plugin_type="unknown",
                description="Invalid plugin manifest",
            )
            return PluginRecord(
                manifest=fallback,
                path=path.parent,
                source=source,
                state=PluginState.ERROR,
                warnings=(str(exc),),
            )

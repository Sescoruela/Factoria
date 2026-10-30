from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from pathlib import Path

from factoria.domain.models import PluginManifest, PluginType

from .compatibility import is_compatible


_VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class PluginConflictError(RuntimeError):
    """Raised when two plugins with the same priority register the same name."""


class PluginSource(IntEnum):
    BUILTIN = 100
    ORGANIZATION = 200
    PERSONAL = 300


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


@dataclass(frozen=True, slots=True)
class ShadowedPlugin:
    selected: PluginRecord
    shadowed: PluginRecord


class PluginRegistry:
    def __init__(self, *, factoria_version: str = "0.1.0") -> None:
        self._factoria_version = factoria_version
        self._plugins: dict[str, PluginRecord] = {}
        self._problems: list[PluginRecord] = []
        self._shadowed: list[ShadowedPlugin] = []

    @property
    def plugins(self) -> tuple[PluginRecord, ...]:
        return tuple(sorted(self._plugins.values(), key=lambda record: record.manifest.name))

    @property
    def problems(self) -> tuple[PluginRecord, ...]:
        return tuple(self._problems)

    @property
    def shadowed(self) -> tuple[ShadowedPlugin, ...]:
        return tuple(self._shadowed)

    def register(self, record: PluginRecord) -> None:
        if record.state is PluginState.ERROR:
            self._problems.append(record)
            return

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
            self._shadowed.append(ShadowedPlugin(selected=record, shadowed=existing))
            self._plugins[record.manifest.name] = record
        else:
            self._shadowed.append(ShadowedPlugin(selected=existing, shadowed=record))

    def discover(self, roots: list[tuple[PluginSource, Path]]) -> tuple[PluginRecord, ...]:
        for source, root in roots:
            if not root.exists():
                continue
            if not root.is_dir():
                self._problems.append(
                    self._error_record(root, source, "Plugin source is not a directory")
                )
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
                raw = tomllib.load(handle)

            plugin_table = raw.get("plugin")
            deprecated_layout = plugin_table is None
            data = raw if deprecated_layout else plugin_table
            if not isinstance(data, dict):
                raise ValueError("[plugin] must be a TOML table")

            required = ("name", "version", "type", "description")
            missing = tuple(
                key
                for key in required
                if not isinstance(data.get(key), str) or not data[key].strip()
            )
            if missing:
                raise ValueError(f"Missing required fields: {', '.join(missing)}")

            version = data["version"].strip()
            if not _VERSION_RE.fullmatch(version):
                raise ValueError("version must use semantic versioning (MAJOR.MINOR.PATCH)")

            try:
                plugin_type = PluginType(data["type"].strip())
            except ValueError as exc:
                allowed = ", ".join(item.value for item in PluginType)
                raise ValueError(f"type must be one of: {allowed}") from exc

            capabilities = data.get("capabilities", [])
            if not isinstance(capabilities, list) or not all(
                isinstance(item, str) and item.strip() for item in capabilities
            ):
                raise ValueError("capabilities must be a list of non-empty strings")

            compatibility = raw.get("compatibility", {})
            if compatibility is None:
                compatibility = {}
            if not isinstance(compatibility, dict):
                raise ValueError("[compatibility] must be a TOML table")
            factoria = compatibility.get("factoria", ">=0.1.0")
            if not isinstance(factoria, str) or not factoria.strip():
                raise ValueError("compatibility.factoria must be a non-empty string")
            if not is_compatible(self._factoria_version, factoria):
                raise ValueError(
                    f"Requires Factoria {factoria}; current version is {self._factoria_version}"
                )

            entrypoint = data.get("entrypoint")
            if entrypoint is not None and (
                not isinstance(entrypoint, str) or not entrypoint.strip()
            ):
                raise ValueError("entrypoint must be a non-empty string")
            if entrypoint is not None and not (path.parent / entrypoint).is_file():
                raise ValueError(f"Entrypoint does not exist: {entrypoint}")

            warnings: list[str] = []
            if deprecated_layout:
                warnings.append(
                    "Top-level plugin fields are deprecated; move them under [plugin]"
                )

            manifest = PluginManifest(
                name=data["name"].strip(),
                version=version,
                plugin_type=plugin_type,
                description=data["description"].strip(),
                capabilities=tuple(item.strip() for item in capabilities),
                factoria_compatibility=factoria,
                entrypoint=entrypoint,
            )
            return PluginRecord(
                manifest=manifest,
                path=path.parent,
                source=source,
                state=PluginState.WARNING if warnings else PluginState.VALID,
                warnings=tuple(warnings),
            )
        except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
            return self._error_record(path.parent, source, str(exc))

    def _error_record(
        self,
        path: Path,
        source: PluginSource,
        message: str,
    ) -> PluginRecord:
        fallback = PluginManifest(
            name=path.name,
            version="0.0.0",
            plugin_type=PluginType.CHECK,
            description="Invalid plugin manifest",
        )
        return PluginRecord(
            manifest=fallback,
            path=path,
            source=source,
            state=PluginState.ERROR,
            warnings=(message,),
        )

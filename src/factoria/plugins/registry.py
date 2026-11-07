from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field, replace
from enum import IntEnum, StrEnum
from pathlib import Path

from factoria.domain.models import PluginManifest, PluginType

from .compatibility import is_compatible


_VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class PluginConflictError(RuntimeError):
    """Backward-compatible error type for callers that handle plugin conflicts."""


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
        self._blocked_priority: dict[str, PluginSource] = {}

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

        name = record.manifest.name
        blocked = self._blocked_priority.get(name)
        if blocked is not None:
            if record.source > blocked:
                del self._blocked_priority[name]
            else:
                self._problems.append(
                    self._as_error(
                        record,
                        f"Plugin '{name}' remains blocked by a same-priority collision at "
                        f"{blocked.name.lower()} priority",
                    )
                )
                return

        existing = self._plugins.get(name)
        if existing is None:
            self._plugins[name] = record
            return

        if existing.source == record.source:
            self._plugins.pop(name, None)
            message = (
                f"Plugin '{name}' is defined more than once at priority "
                f"{record.source.name.lower()}; neither definition will load"
            )
            self._problems.extend(
                (self._as_error(existing, message), self._as_error(record, message))
            )
            self._blocked_priority[name] = record.source
            return

        if record.source > existing.source:
            self._shadowed.append(ShadowedPlugin(selected=record, shadowed=existing))
            self._plugins[name] = record
        else:
            self._shadowed.append(ShadowedPlugin(selected=existing, shadowed=record))

    def discover(self, roots: list[tuple[PluginSource, Path]]) -> tuple[PluginRecord, ...]:
        for source, root in roots:
            root = root.expanduser().resolve()
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
            if entrypoint is not None:
                plugin_root = path.parent.resolve()
                target = (plugin_root / entrypoint).resolve()
                try:
                    target.relative_to(plugin_root)
                except ValueError as exc:
                    raise ValueError("entrypoint must stay inside the plugin directory") from exc
                if not target.is_file():
                    raise ValueError(f"Entrypoint does not exist: {entrypoint}")

            warnings: list[str] = []
            if deprecated_layout:
                warnings.append("Top-level plugin fields are deprecated; move them under [plugin]")
            if entrypoint is not None and source is not PluginSource.BUILTIN:
                warnings.append(
                    "External entrypoint is trusted Python code and will execute in the Factoria process"
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
                path=path.parent.resolve(),
                source=source,
                state=PluginState.WARNING if warnings else PluginState.VALID,
                warnings=tuple(warnings),
            )
        except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
            return self._error_record(path.parent, source, str(exc))

    @staticmethod
    def _as_error(record: PluginRecord, message: str) -> PluginRecord:
        return replace(record, state=PluginState.ERROR, warnings=record.warnings + (message,))

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
            path=path.resolve(),
            source=source,
            state=PluginState.ERROR,
            warnings=(message,),
        )

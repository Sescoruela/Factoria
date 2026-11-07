from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import uuid4

from factoria.config.loader import load_global_config

from .registry import (
    PluginRecord,
    PluginRegistry,
    PluginSource,
    PluginState,
    ShadowedPlugin,
)


class PluginLoadError(RuntimeError):
    """Raised when executable plugin code cannot be loaded."""


@dataclass(frozen=True, slots=True)
class LoadedPlugin:
    record: PluginRecord
    module: ModuleType | None
    instance: Any = None


def load_plugin(record: PluginRecord) -> LoadedPlugin:
    """Load trusted plugin code after discovery and manifest validation.

    Entrypoints execute arbitrary Python in the current Factoria process. Configuring
    an external plugin path is therefore an explicit trust decision, not a sandbox.
    """
    if record.state is PluginState.ERROR:
        raise PluginLoadError(f"Cannot load invalid plugin '{record.manifest.name}'")

    entrypoint = record.manifest.entrypoint
    if entrypoint is None:
        return LoadedPlugin(record=record, module=None)

    root = record.path.resolve()
    path = (root / entrypoint).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PluginLoadError("Plugin entrypoint escapes its plugin directory") from exc

    module_name = f"factoria_plugin_{record.manifest.name}_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise PluginLoadError(f"Cannot create module spec for {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        factory = getattr(module, "load_plugin", None)
        if factory is None or not callable(factory):
            raise PluginLoadError(
                f"Plugin '{record.manifest.name}' entrypoint must expose callable load_plugin()"
            )
        instance = factory()
    except Exception as exc:
        sys.modules.pop(module_name, None)
        if isinstance(exc, PluginLoadError):
            raise
        raise PluginLoadError(
            f"Plugin '{record.manifest.name}' failed during load: {type(exc).__name__}: {exc}"
        ) from exc

    return LoadedPlugin(record=record, module=module, instance=instance)


def load_plugins(records: tuple[PluginRecord, ...]) -> tuple[LoadedPlugin, ...]:
    """Load all discovered plugins in deterministic name order."""
    return tuple(
        load_plugin(record)
        for record in sorted(records, key=lambda item: item.manifest.name.casefold())
    )


@dataclass(frozen=True, slots=True)
class PluginRuntimeReport:
    loaded: tuple[LoadedPlugin, ...]
    problems: tuple[PluginRecord, ...]
    shadowed: tuple[ShadowedPlugin, ...]


@dataclass(frozen=True, slots=True)
class PluginRuntime:
    factoria_version: str
    builtin_root: Path | None = None

    def configured_roots(self) -> list[tuple[PluginSource, Path]]:
        config = load_global_config(Path.home() / ".factoria" / "config.toml")
        roots: list[tuple[PluginSource, Path]] = []
        roots.extend((PluginSource.PERSONAL, path) for path in config.personal_plugin_paths)
        roots.extend((PluginSource.ORGANIZATION, path) for path in config.organization_plugin_paths)
        builtin = self.builtin_root
        if builtin is None:
            candidate = Path(__file__).resolve().parent / "builtin"
            if candidate.is_dir():
                builtin = candidate
        if builtin is not None:
            roots.append((PluginSource.BUILTIN, builtin))
        return roots

    def discover_and_load(
        self,
        *,
        extra_roots: list[tuple[PluginSource, Path]] | None = None,
    ) -> PluginRuntimeReport:
        registry = PluginRegistry(factoria_version=self.factoria_version)
        roots = self.configured_roots()
        if extra_roots:
            roots.extend(extra_roots)
        registry.discover(roots)

        loaded: list[LoadedPlugin] = []
        problems = list(registry.problems)
        for record in registry.plugins:
            try:
                loaded.append(load_plugin(record))
            except PluginLoadError as exc:
                problems.append(
                    PluginRecord(
                        manifest=record.manifest,
                        path=record.path,
                        source=record.source,
                        state=PluginState.ERROR,
                        warnings=record.warnings + (str(exc),),
                    )
                )

        return PluginRuntimeReport(
            loaded=tuple(loaded),
            problems=tuple(problems),
            shadowed=registry.shadowed,
        )

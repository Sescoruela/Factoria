from __future__ import annotations

from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from types import ModuleType
from uuid import uuid4

from .registry import PluginRecord, PluginState


class PluginLoadError(RuntimeError):
    """Raised when executable plugin code cannot be loaded."""


@dataclass(frozen=True, slots=True)
class LoadedPlugin:
    record: PluginRecord
    module: ModuleType | None


def load_plugin(record: PluginRecord) -> LoadedPlugin:
    """Load a trusted plugin after discovery and validation.

    Plugin entrypoints execute arbitrary Python in the current process.
    """
    if record.state is PluginState.ERROR:
        raise PluginLoadError(f"Cannot load invalid plugin '{record.manifest.name}'")

    entrypoint = record.manifest.entrypoint
    if entrypoint is None:
        return LoadedPlugin(record=record, module=None)

    path = record.path / entrypoint
    module_name = f"factoria_plugin_{record.manifest.name}_{uuid4().hex}"
    spec = spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise PluginLoadError(f"Cannot create module spec for {path}")

    module = module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise PluginLoadError(
            f"Plugin '{record.manifest.name}' failed during load: {exc}"
        ) from exc

    return LoadedPlugin(record=record, module=module)


def load_plugins(records: tuple[PluginRecord, ...]) -> tuple[LoadedPlugin, ...]:
    """Load all discovered plugins in deterministic name order."""
    return tuple(
        load_plugin(record)
        for record in sorted(records, key=lambda item: item.manifest.name.casefold())
    )

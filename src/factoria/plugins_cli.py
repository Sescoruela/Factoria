from __future__ import annotations

import argparse
from pathlib import Path

from factoria.package_version import installed_version_text
from factoria.plugins.registry import PluginSource
from factoria.plugins.runtime import PluginRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factoria")
    parser.add_argument("--project", default=".")
    parser.add_argument("--profile")
    parser.add_argument("--read-only", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    plugins = sub.add_parser("plugins", help="Discover and load configured Factoria plugins")
    plugins.add_argument("--personal", action="append", default=[])
    plugins.add_argument("--organization", action="append", default=[])
    plugins.add_argument("--builtin", action="append", default=[])
    return parser


def run_plugins_cli(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    runtime = PluginRuntime(factoria_version=installed_version_text())
    extras: list[tuple[PluginSource, Path]] = []
    extras.extend(
        (PluginSource.PERSONAL, Path(item).expanduser().resolve())
        for item in args.personal
    )
    extras.extend(
        (PluginSource.ORGANIZATION, Path(item).expanduser().resolve())
        for item in args.organization
    )
    extras.extend(
        (PluginSource.BUILTIN, Path(item).expanduser().resolve())
        for item in args.builtin
    )
    report = runtime.discover_and_load(extra_roots=extras)

    if report.loaded:
        print("Plugins cargados:")
        for loaded in report.loaded:
            record = loaded.record
            code = "python" if loaded.module is not None else "metadata"
            print(
                f"- {record.manifest.name} {record.manifest.version} | "
                f"{record.manifest.plugin_type.value} | {record.state.value} | "
                f"{record.source.name.lower()} | {code} | {record.path}"
            )
            for warning in record.warnings:
                print(f"  aviso: {warning}")
    else:
        print("Plugins cargados: ninguno")

    if report.shadowed:
        print("Plugins sombreados:")
        for item in report.shadowed:
            print(
                f"- {item.shadowed.manifest.name}: "
                f"{item.shadowed.source.name.lower()} -> "
                f"{item.selected.source.name.lower()}"
            )

    if report.problems:
        print("Problemas:")
        for record in report.problems:
            details = "; ".join(record.warnings) or "error desconocido"
            print(
                f"- ERROR {record.manifest.name} | "
                f"{record.source.name.lower()} | {record.path} | {details}"
            )
        return 1

    return 0

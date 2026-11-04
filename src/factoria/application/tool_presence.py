"""Passive UI metadata: filesystem/PATH only, never start an agent executable."""
from __future__ import annotations

import shutil

from factoria.adapters.codex_discovery import discover_codex


def tool_presence() -> list[dict[str, object]]:
    codex = discover_codex()
    opencode = shutil.which('opencode')
    return [
        {'name': 'codex', 'available': codex.cli_path is not None, 'ready': False,
         'external_start': True, 'checks': [], 'cli_source': codex.cli_source,
         'desktop_detected': codex.desktop_detected, 'desktop_hint': codex.desktop_hint},
        {'name': 'opencode', 'available': opencode is not None, 'ready': False,
         'external_start': True, 'checks': []},
    ]


def assert_ui_command_allowed(args: list[str]) -> None:
    """Block provider startup, including commands prefixed with global CLI options."""
    index = 0
    while index < len(args):
        value = args[index]
        if value in {'--project', '--profile'}:
            index += 2
            continue
        if value == '--read-only' or value.startswith(('--project=', '--profile=')):
            index += 1
            continue
        break
    command = args[index] if index < len(args) else None
    if command in {'feature', 'fix', 'resume', 'install', 'ui', 'web', 'tui', 'onboarding'}:
        raise ValueError('Inicia y configura Codex/OpenCode fuera de Factoría. La aplicación prepara los proyectos; no arranca sus CLIs.')

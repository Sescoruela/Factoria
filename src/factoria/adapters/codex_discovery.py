from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CodexDiscovery:
    cli_path: Path | None
    cli_source: str | None
    desktop_detected: bool
    desktop_hint: str | None = None


def discover_codex() -> CodexDiscovery:
    """Resolve Codex CLI using stable user intent first, desktop runtime heuristics last.

    Order:
    1. CODEX_CLI_PATH explicitly supplied by the user/environment.
    2. `codex` available on PATH.
    3. A relocated ChatGPT Desktop Codex runtime under LOCALAPPDATA on Windows.

    The desktop-runtime path is a heuristic rather than a documented public contract,
    so callers must still run the normal Factoria self-tests before declaring it ready.
    """
    desktop, hint = _desktop_details()
    explicit = os.environ.get("CODEX_CLI_PATH", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file():
            return CodexDiscovery(path.resolve(), "CODEX_CLI_PATH", desktop, hint)

    which = shutil.which("codex")
    if which:
        return CodexDiscovery(Path(which).resolve(), "PATH", desktop, hint)

    runtime = _desktop_runtime_cli()
    if runtime is not None:
        return CodexDiscovery(runtime, "ChatGPT Desktop runtime", True, hint)
    return CodexDiscovery(None, None, desktop, hint)


def _desktop_runtime_cli() -> Path | None:
    if sys.platform != "win32":
        return None
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    root = Path(local)
    candidates = (
        root / "OpenAI" / "Codex" / "bin" / "codex.exe",
        root / "OpenAI" / "ChatGPT" / "bin" / "codex.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def _desktop_details() -> tuple[bool, str | None]:
    """Find local installation traces, never authentication or an active session.

    Windows package-data folders can survive uninstall. These filesystem hints
    must not be presented as verified availability of Codex inside ChatGPT.
    """
    if sys.platform != "win32":
        return False, None
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return False, None
    root = Path(local)
    candidates = [
        root / "OpenAI" / "Codex",
        root / "OpenAI" / "ChatGPT",
        root / "Programs" / "ChatGPT",
        root / "Programs" / "OpenAI" / "ChatGPT",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return True, str(candidate)
    packages = root / "Packages"
    if packages.is_dir():
        try:
            for path in sorted(packages.iterdir()):
                if path.is_dir() and path.name.lower().startswith(
                    ("openai.chatgpt", "openai.codex")
                ):
                    return True, str(path)
        except OSError:
            pass
    return False, None

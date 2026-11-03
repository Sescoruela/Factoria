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
    """Discover a supported Codex CLI without treating desktop internals as public API.

    Resolution order is explicit CODEX_CLI_PATH, normal PATH, then detection-only
    of the ChatGPT/Codex desktop runtime. Desktop detection is informational: Factoria
    does not execute a bundled/private desktop binary automatically.
    """
    explicit = os.environ.get("CODEX_CLI_PATH", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file():
            return CodexDiscovery(path.resolve(), "CODEX_CLI_PATH", _desktop_detected())

    which = shutil.which("codex")
    if which:
        return CodexDiscovery(Path(which).resolve(), "PATH", _desktop_detected())

    desktop, hint = _desktop_details()
    return CodexDiscovery(None, None, desktop, hint)


def _desktop_detected() -> bool:
    return _desktop_details()[0]


def _desktop_details() -> tuple[bool, str | None]:
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
    ]
    for candidate in candidates:
        if candidate.exists():
            return True, str(candidate)
    packages = root / "Packages"
    if packages.is_dir():
        try:
            if any(path.name.lower().startswith(("openai.chatgpt", "openai.codex")) for path in packages.iterdir()):
                return True, str(packages)
        except OSError:
            pass
    return False, None

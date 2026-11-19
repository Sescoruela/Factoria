"""Keep generated workspace files local to a Git checkout."""

import subprocess
from collections.abc import Iterable
from pathlib import Path
from threading import Lock

_RULES = (
    b"/.factoria/",
    b"/.agents/skills/factoria-*/",
    b"/.opencode/commands/factoria-*.md",
    b"/.opencode/agents/factoria-*.md",
)
_EXCLUDE_LOCK = Lock()


def _git(root: Path, *args: str, data: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        input=data,
        capture_output=True,
        check=False,
    )


def _checkout(root: Path) -> tuple[Path, Path] | None:
    root = root.resolve()
    if not (root / ".git").exists():
        return None
    result = _git(root, "rev-parse", "--show-toplevel", "--git-path", "info/exclude")
    result.check_returncode()
    top, exclude = result.stdout.decode("utf-8").splitlines()
    if Path(top).resolve() != root:
        return None
    return root, root / exclude


def tracked_project_files(root: Path, paths: Iterable[str]) -> set[str]:
    paths = tuple(paths)
    if not paths or _checkout(root) is None:
        return set()
    result = _git(root, "--literal-pathspecs", "ls-files", "-z", "--cached", "--", *paths)
    result.check_returncode()
    return set(result.stdout.decode("utf-8").split("\0")) - {""}


def unignored_project_files(root: Path, paths: Iterable[str]) -> set[str]:
    paths = set(paths)
    if not paths or _checkout(root) is None:
        return set()
    data = b"".join(path.encode("utf-8") + b"\0" for path in sorted(paths))
    result = _git(root, "check-ignore", "--no-index", "-z", "--stdin", data=data)
    if result.returncode not in (0, 1):
        result.check_returncode()
    return paths - set(result.stdout.decode("utf-8").split("\0"))


def ensure_local_project_files(root: Path, paths: Iterable[str] = ()) -> None:
    """Exclude new files locally. Protect managed files already tracked by Git."""
    checkout = _checkout(root)
    if checkout is None:
        return
    root, exclude = checkout
    paths = tuple(paths)
    tracked = tracked_project_files(root, paths)
    if tracked:
        raise ValueError(
            "Git ya sigue estos archivos. Retíralos del índice sin borrarlos antes de guardarlos "
            "como configuración local: " + ", ".join(sorted(tracked))
        )

    extra = tuple(
        f"/{path}".encode("utf-8")
        for path in sorted(paths)
        if path == "AGENTS.md" or path.startswith("docs/memoria/")
    )
    with _EXCLUDE_LOCK:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a+b") as stream:
            stream.seek(0)
            current = stream.read()
            existing = set(current.splitlines())
            missing = [rule for rule in dict.fromkeys((*_RULES, *extra)) if rule not in existing]
            if missing:
                newline = b"\r\n" if b"\r\n" in current else b"\n"
                if current and not current.endswith(b"\n"):
                    stream.write(newline)
                stream.write(newline.join((b"# factoria: archivos locales", *missing, b"")))
    visible = unignored_project_files(root, paths)
    if visible:
        raise ValueError(
            "Las reglas Git del repositorio vuelven a incluir estos archivos. Revisa .gitignore: "
            + ", ".join(sorted(visible))
        )

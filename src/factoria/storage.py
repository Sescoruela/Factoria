"""Filesystem primitives only; callers own paths, policy, revisions and transactions."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile


@contextmanager
def staged_bytes(target: Path, content: bytes) -> Iterator[Path]:
    """Flush a sibling temporary file and remove it on every exit, including write failure.

    The caller can check its optimistic revision after staging and before publication.
    This does not grant permission or make multiple files a filesystem transaction.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        yield temporary
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_write_bytes(target: Path, content: bytes, *, create: bool = False) -> None:
    """Publish one file; exclusive creation never overwrites a competing writer."""
    with staged_bytes(target, content) as temporary:
        if create:
            os.link(temporary, target)
        else:
            os.replace(temporary, target)


def sync_directory(path: Path) -> None:
    """Synchronize directory metadata on POSIX; retain the existing Windows behavior."""
    if os.name == "posix":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

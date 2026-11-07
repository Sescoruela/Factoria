"""Project path containment shared by config and application; filesystem only."""

from pathlib import Path


def project_path(root: Path, relative: str) -> Path:
    """Reject traversal, symlink targets and Windows drive paths on every OS."""
    from pathlib import PurePosixPath, PureWindowsPath

    if (
        not relative
        or "\\" in relative
        or PurePosixPath(relative).is_absolute()
        or PureWindowsPath(relative).drive
        or ".." in PurePosixPath(relative).parts
    ):
        raise ValueError("La ruta debe ser relativa al proyecto")
    root = root.resolve()
    target = root / relative
    for item in (target, *target.parents):
        if item == root:
            break
        if item.is_symlink():
            raise ValueError("La integración no sigue enlaces simbólicos")
    if not target.resolve().is_relative_to(root):
        raise ValueError("Ruta fuera del proyecto")
    return target

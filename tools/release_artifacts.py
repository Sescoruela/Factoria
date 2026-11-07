"""Offline release metadata and SHA-256 checks; never downloads or executes assets."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sys
import tomllib


def check_version(root: Path) -> str:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    release = tomllib.loads((root / "src/factoria/release.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version) or release.get("version") != version:
        raise ValueError("project.version and release.toml must match a stable X.Y.Z version")
    return version


def _asset(directory: Path, name: str) -> Path:
    if not name or name in {".", "..", "SHA256SUMS"} or re.search(r"[\\/:\s]", name):
        raise ValueError(f"Invalid asset filename: {name!r}")
    path = directory / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Asset must be a nonempty regular file: {name}")
    return path


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_checksums(directory: Path, names: list[str]) -> Path:
    if not names or len(set(names)) != len(names):
        raise ValueError("Provide a nonempty list of distinct asset filenames")
    # Validate every asset before writing or replacing any manifest.
    lines = [f"{_digest(_asset(directory, name))}  {name}\n" for name in sorted(names)]
    target = directory / "SHA256SUMS"
    if target.is_symlink():
        raise ValueError("Refusing symlink manifest")
    target.write_text("".join(lines), encoding="ascii", newline="\n")
    return target


def verify_checksums(directory: Path) -> list[str]:
    manifest = directory / "SHA256SUMS"
    if manifest.is_symlink():
        raise ValueError("Refusing symlink manifest")
    lines = manifest.read_text(encoding="ascii").splitlines()
    if not lines:
        raise ValueError("Empty checksum manifest")
    names: list[str] = []
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ValueError("Malformed checksum manifest")
        digest, name = match.groups()
        if name in names:
            raise ValueError("Duplicate checksum asset")
        if _digest(_asset(directory, name)) != digest:
            raise ValueError(f"SHA-256 mismatch: {name}")
        names.append(name)
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    version = sub.add_parser("version")
    version.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    sums = sub.add_parser("checksums")
    sums.add_argument("directory", type=Path)
    sums.add_argument("assets", nargs="+")
    verify = sub.add_parser("verify")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "version":
            print(check_version(args.root))
        elif args.command == "checksums":
            print(write_checksums(args.directory, args.assets))
        else:
            for name in verify_checksums(args.directory):
                print(f"PASS {name}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

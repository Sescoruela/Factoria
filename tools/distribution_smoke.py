"""Install two locally built wheels in an isolated venv and preserve project data.

Developer tool: installs only explicitly supplied trusted local wheels; no downloads,
provider starts, user-home writes or publication. Does not certify Windows upgrades.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

from factoria.versioning import SemVer


def run(command, *, env=None) -> str:
    result = subprocess.run(
        [str(arg) for arg in command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )
    if result.returncode:
        raise RuntimeError(
            f"Command failed: {command}\n{result.stderr[-2000:]}\n{result.stdout[-1000:]}"
        )
    return result.stdout.strip()


def snapshot(*roots: Path) -> dict[str, str]:
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for root in roots
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


def smoke(previous: Path, candidate: Path, report: Path) -> dict:
    for wheel in (previous, candidate):
        if not wheel.is_file() or wheel.suffix != ".whl":
            raise ValueError("Provide two trusted local wheel files")
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="factoria-distribution-") as temp:
        lab = Path(temp)
        venv.EnvBuilder(with_pip=True).create(lab / "venv")
        scripts = lab / "venv" / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        executable = scripts / ("factoria.exe" if os.name == "nt" else "factoria")
        home = lab / "home"
        (home / ".factoria").mkdir(parents=True)
        (home / ".factoria/config.toml").write_text('default_profile = "normal"\n')
        env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
        run(
            [python, "-m", "pip", "install", "--no-index", "--no-deps", previous.resolve()], env=env
        )
        before_version = run([executable, "--version"], env=env)
        run(
            [
                sys.executable,
                root / "tools/acceptance_lab.py",
                "prepare",
                lab / "projects",
                "--python-command",
                python,
            ],
            env=env,
        )
        project = lab / "projects/chatgpt-checkout/feature"
        run([executable, "--project", project, "project", "check"], env=env)
        before = snapshot(project, home)
        run(
            [
                python,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--upgrade",
                candidate.resolve(),
            ],
            env=env,
        )
        after_version = run([executable, "--version"], env=env)
        if SemVer.parse(after_version.removeprefix("factoria ")) <= SemVer.parse(
            before_version.removeprefix("factoria ")
        ):
            raise ValueError("Upgrade smoke requires a newer candidate version")
        for _ in range(2):
            run([executable, "--project", project, "project", "check"], env=env)
        catalog = json.loads(
            run([executable, "--project", project, "project", "workflows"], env=env)
        )
        if not any(item["id"] == "feature-lab" for item in catalog["workflows"]):
            raise ValueError("Custom workflow missing after upgrade")
        if before != snapshot(project, home):
            raise ValueError("Project or user data changed during upgrade/reopen")
        run(
            [
                python,
                "-c",
                "from importlib.resources import files; "
                "assert files('factoria').joinpath('release.toml').is_file(); "
                "assert files('factoria.web').joinpath('workflows.js').is_file()",
            ],
            env=env,
        )
        result = {
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "previous": before_version,
            "candidate": after_version,
            "upgrade_and_reopen_twice": "PASS",
            "files_preserved": len(before),
            "custom_workflow": "feature-lab",
            "resources": "PASS",
            "previous_wheel_sha256": hashlib.sha256(previous.read_bytes()).hexdigest(),
            "candidate_wheel_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
            "limits": "Local wheel smoke only; not a tagged release, installer or provider acceptance.",
        }
        report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("previous_wheel", type=Path)
    parser.add_argument("candidate_wheel", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(smoke(args.previous_wheel, args.candidate_wheel, args.report), indent=2))

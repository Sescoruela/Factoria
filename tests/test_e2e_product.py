from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


@unittest.skipIf(os.name == 'nt', 'POSIX fake-agent executable; native project journeys run on Windows in test_project_integration')
class ProductEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="factoria-e2e-")
        self.root = Path(self.temp.name)
        self.repo = self.root / "project"
        self.bin = self.root / "bin"
        self.home = self.root / "home"
        self.repo.mkdir()
        self.bin.mkdir()
        self.home.mkdir()
        self._write_fixture_project()
        self._write_fake_opencode()
        self._git("init", "-b", "main")
        self._git("config", "user.name", "Factoria E2E")
        self._git("config", "user.email", "factoria-e2e@example.invalid")
        self._git("add", ".")
        self._git("commit", "-m", "Initial fixture")

        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env.get("PATH", "")
        for profile in ("RAPIDO", "EQUILIBRADO", "POTENTE"):
            self.env[f"FACTORIA_OPENCODE_{profile}"] = "fixture-model"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_feature_full_product_journey(self) -> None:
        self._bootstrap_memory()

        started = self._factoria(
            "feature",
            "Change greeting to hello world",
            "--branch",
            "feature/e2e",
            "--tool",
            "opencode",
        )
        flow_id = self._flow_id(started.stdout, "feature")
        self.assertIn("Estado: paused", started.stdout)
        self.assertIn("awaiting_plan_approval", started.stdout)
        self.assertTrue((self.repo / ".factoria" / "work" / flow_id / "plan.md").exists())

        implemented = self._factoria("resume", flow_id, "--approve-plan")
        self.assertIn("-> paused", implemented.stdout)
        self.assertEqual('def greeting():\n    return "hello world"\n', (self.repo / "src" / "app.py").read_text())
        verification = (self.repo / ".factoria" / "work" / flow_id / "verification.md").read_text()
        self.assertIn("PASS", verification)
        review = (self.repo / ".factoria" / "work" / flow_id / "review.json").read_text()
        self.assertIn('"result": "approved"', review)

        approved = self._factoria("resume", flow_id, "--approve-final")
        self.assertIn("-> paused", approved.stdout)

        committed = self._factoria("commit", flow_id, "--yes")
        self.assertIn("Commit creado:", committed.stdout)
        self.assertIn("Flujo cerrado", committed.stdout)
        self.assertEqual("", self._git("status", "--porcelain").stdout.strip())
        self.assertEqual("feat: Change greeting to hello world", self._git("log", "-1", "--pretty=%s").stdout.strip())

        history = self._factoria("history", "--flow-id", flow_id, "--report")
        self.assertIn(flow_id, history.stdout)
        self.assertIn("completed", history.stdout)
        self.assertIn("opencode", history.stdout)
        self.assertIn("fixture-model", history.stdout)

        status = self._factoria("status")
        self.assertIn("FACTORIA STATUS", status.stdout)
        self.assertIn("Flujos activos", status.stdout)
        self.assertIn("Ninguno", status.stdout)

    def test_small_fix_runs_without_feature_approval_gates(self) -> None:
        self._bootstrap_memory()

        started = self._factoria(
            "fix",
            "Fix greeting output",
            "--branch",
            "fix/e2e",
            "--tool",
            "opencode",
        )
        flow_id = self._flow_id(started.stdout, "fix")
        self.assertIn("Estado: paused", started.stdout)
        self.assertIn("ready_for_commit", started.stdout)
        self.assertIn("PASS", (self.repo / ".factoria" / "work" / flow_id / "verification.md").read_text())

        committed = self._factoria("commit", flow_id, "--yes")
        self.assertIn("Flujo cerrado", committed.stdout)
        self.assertEqual("fix: Fix greeting output", self._git("log", "-1", "--pretty=%s").stdout.strip())

    def _bootstrap_memory(self) -> None:
        preview = self._factoria("memoria-init", "--kind", "active")
        self.assertIn("Propuesta no escrita", preview.stdout)
        self.assertFalse((self.repo / "AGENTS.md").exists())

        applied = self._factoria("memoria-init", "--kind", "active", "--yes")
        self.assertIn("Escrito: AGENTS.md", applied.stdout)
        self.assertTrue((self.repo / "AGENTS.md").exists())
        self.assertTrue((self.repo / ".factoria" / "config.toml").exists())
        self._git("add", ".")
        self._git("commit", "-m", "Initialize Factoria memory")
        self.assertEqual("", self._git("status", "--porcelain").stdout.strip())

    def _factoria(self, *args: str) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, "-m", "factoria", "--project", str(self.repo), *args],
            cwd=self.repo,
            env=self.env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if completed.returncode != 0:
            self.fail(
                "Factoria command failed:\n"
                + " ".join(args)
                + f"\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        return completed

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    @staticmethod
    def _flow_id(output: str, kind: str) -> str:
        match = re.search(rf"{kind} iniciado: ([0-9a-f-]+)", output)
        if match is None:
            raise AssertionError(f"Flow id not found in output:\n{output}")
        return match.group(1)

    def _write_fixture_project(self) -> None:
        (self.repo / "src").mkdir()
        (self.repo / "tests").mkdir()
        (self.repo / "src" / "__init__.py").write_text("", encoding="utf-8")
        (self.repo / "src" / "app.py").write_text(
            'def greeting():\n    return "hello"\n', encoding="utf-8"
        )
        (self.repo / "tests" / "test_app.py").write_text(
            textwrap.dedent(
                """
                import unittest
                from src.app import greeting


                class GreetingTests(unittest.TestCase):
                    def test_greeting(self):
                        self.assertEqual("hello", greeting())


                if __name__ == "__main__":
                    unittest.main()
                """
            ).lstrip(),
            encoding="utf-8",
        )
        (self.repo / "pyproject.toml").write_text(
            '[project]\nname = "fixture-project"\nversion = "0.0.0"\n', encoding="utf-8"
        )
        (self.repo / ".gitignore").write_text(
            ".factoria/work/\n.factoria/security/\n__pycache__/\n*.pyc\n",
            encoding="utf-8",
        )

    def _write_fake_opencode(self) -> None:
        executable = self.bin / "opencode"
        executable.write_text(
            textwrap.dedent(
                r'''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
if args == ["--version"]:
    print("opencode fixture 1.0")
    raise SystemExit(0)
if args == ["run", "--help"]:
    print("usage: opencode run --dir PATH --format FORMAT --model MODEL")
    raise SystemExit(0)
if args == ["debug", "config"]:
    raw = os.environ.get("OPENCODE_CONFIG_CONTENT", "{}")
    print(raw)
    raise SystemExit(0)
if not args or args[0] != "run":
    print("unsupported fake opencode invocation", file=sys.stderr)
    raise SystemExit(2)

try:
    root = Path(args[args.index("--dir") + 1])
except (ValueError, IndexError):
    print("missing --dir", file=sys.stderr)
    raise SystemExit(2)
prompt = args[-1]
role = "unknown"
for candidate in ("explorer", "planner", "implementer", "reviewer", "documenter"):
    if f"You are the {candidate}" in prompt:
        role = candidate
        break

try:
    runtime = json.loads(os.environ.get("OPENCODE_CONFIG_CONTENT", "{}"))
except json.JSONDecodeError:
    print("invalid runtime config", file=sys.stderr)
    raise SystemExit(3)
permission = runtime.get("permission", {})
if permission.get("*") != "deny":
    print("deny-by-default permission missing", file=sys.stderr)
    raise SystemExit(4)
if role == "implementer":
    if permission.get("edit") != "allow":
        print("implementer edit permission missing", file=sys.stderr)
        raise SystemExit(5)
    (root / "src" / "app.py").write_text('def greeting():\n    return "hello world"\n', encoding="utf-8")
    (root / "tests" / "test_app.py").write_text(
        'import unittest\nfrom src.app import greeting\n\nclass GreetingTests(unittest.TestCase):\n'
        '    def test_greeting(self):\n        self.assertEqual("hello world", greeting())\n\n'
        'if __name__ == "__main__":\n    unittest.main()\n',
        encoding="utf-8",
    )
    print("implementation complete")
    raise SystemExit(0)
if permission.get("edit") == "allow":
    print("read-only role unexpectedly received edit permission", file=sys.stderr)
    raise SystemExit(6)
if role == "reviewer":
    print(json.dumps({
        "result": "approved",
        "acceptance_criteria_met": True,
        "mandatory_rules_violated": [],
        "findings": [],
        "risks": [],
        "recommendation": "Ready for final approval and commit",
    }))
    raise SystemExit(0)
if role == "planner":
    print("# Plan\n\n1. Update greeting behavior.\n2. Update its unit test.\n3. Run confirmed tests.")
    raise SystemExit(0)
if role == "explorer":
    print("Greeting behavior is isolated to src/app.py and tests/test_app.py.")
    raise SystemExit(0)
if role == "documenter":
    print("No persistent project-memory update required for this behavior-only change.")
    raise SystemExit(0)
print("unknown role", file=sys.stderr)
raise SystemExit(7)
'''
            ),
            encoding="utf-8",
        )
        executable.chmod(0o755)


if __name__ == "__main__":
    unittest.main()

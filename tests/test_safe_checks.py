from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factoria.application.execution import (
    CommandExecution,
    ExecutionMode,
    SafeCheckExecutor,
)
from factoria.domain.models import ConfirmedCommand, ModuleMemory, ProjectMemory


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: ConfirmedCommand, *, cwd: Path, timeout_seconds: int) -> CommandExecution:
        self.commands.append(command.command)
        return CommandExecution(
            name=f"{command.category}:{command.scope or 'global'}:{' '.join(command.command)}",
            category=command.category,
            scope=command.scope,
            command=command.command,
            required=command.required,
            returncode=0,
        )


class SafeCheckExecutorTests(unittest.TestCase):
    def test_read_only_forbids_all_project_commands(self) -> None:
        runner = FakeRunner()
        executor = SafeCheckExecutor(runner=runner)
        memory = ProjectMemory(
            project_name="demo",
            confirmed_check_commands=(
                ConfirmedCommand(category="test", command=("python", "-m", "unittest")),
            ),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(PermissionError):
                executor.execute(
                    memory,
                    project_root=Path(temp_dir),
                    changed_files=("src/app.py",),
                    mode=ExecutionMode.READ_ONLY,
                )
        self.assertEqual(runner.commands, [])

    def test_safe_checks_select_affected_module_and_global_checks(self) -> None:
        runner = FakeRunner()
        executor = SafeCheckExecutor(runner=runner)
        memory = ProjectMemory(
            project_name="demo",
            modules=(
                ModuleMemory(name="backend", paths=("backend",), affects=("shared",)),
                ModuleMemory(name="frontend", paths=("frontend",)),
                ModuleMemory(name="shared", paths=("shared",)),
            ),
            confirmed_check_commands=(
                ConfirmedCommand(
                    category="test",
                    command=("python", "-m", "unittest", "backend"),
                    scope="backend",
                ),
                ConfirmedCommand(
                    category="typecheck",
                    command=("python", "-m", "mypy", "shared"),
                    scope="shared",
                ),
                ConfirmedCommand(
                    category="lint",
                    command=("npm", "run", "lint"),
                    scope="frontend",
                ),
                ConfirmedCommand(
                    category="smoke",
                    command=("python", "scripts/smoke.py"),
                    global_check=True,
                ),
            ),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            summary = executor.execute(
                memory,
                project_root=Path(temp_dir),
                changed_files=("backend/service.py",),
            )

        self.assertEqual(summary.plan.affected_modules, ("backend", "shared"))
        self.assertEqual(
            runner.commands,
            [
                ("python", "-m", "unittest", "backend"),
                ("python", "-m", "mypy", "shared"),
                ("python", "scripts/smoke.py"),
            ],
        )
        self.assertTrue(all(result.passed for result in summary.verification_results))

    def test_categories_filter_confirmed_commands_only(self) -> None:
        runner = FakeRunner()
        executor = SafeCheckExecutor(runner=runner)
        memory = ProjectMemory(
            project_name="demo",
            confirmed_check_commands=(
                ConfirmedCommand(category="build", command=("dotnet", "build")),
                ConfirmedCommand(category="test", command=("dotnet", "test")),
            ),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            executor.execute(
                memory,
                project_root=Path(temp_dir),
                changed_files=("Program.cs",),
                categories=("test",),
            )
        self.assertEqual(runner.commands, [("dotnet", "test")])

    def test_legacy_memory_commands_remain_supported(self) -> None:
        runner = FakeRunner()
        executor = SafeCheckExecutor(runner=runner)
        memory = ProjectMemory(
            project_name="legacy",
            confirmed_commands={"test": (("python", "-m", "unittest"),)},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            executor.execute(
                memory,
                project_root=Path(temp_dir),
                changed_files=("src/x.py",),
            )
        self.assertEqual(runner.commands, [("python", "-m", "unittest")])


if __name__ == "__main__":
    unittest.main()

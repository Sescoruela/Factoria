from __future__ import annotations

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import MappingProxyType
from typing import Iterable

from factoria.config.models import MemoryConfig, ProjectConfig
from factoria.domain.models import (
    ConfirmedCommand,
    MemoryDocumentKind,
    ModuleMemory,
    ProjectKind,
    ProjectMemory,
)
from factoria.domain.permissions import PermissionProfile
from factoria.memory.filesystem import memory_targets, write_initial_memory
from factoria.memory.initializer import GitActivitySnapshot, MemoryInitializer

_PROJECT_CONFIG_MARKER = "# factoria: managed project config"
_STALENESS_DEFAULT = 25
_SCRIPT_CATEGORIES = ("build", "test", "lint", "typecheck", "smoke")
_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class BootstrapEvidence:
    target: str
    reason: str
    source: str


@dataclass(frozen=True, slots=True)
class MemoryBootstrapProposal:
    memory: ProjectMemory
    activity: GitActivitySnapshot
    project_config: ProjectConfig
    config_text: str
    config_target: Path
    write_config: bool
    evidence: tuple[BootstrapEvidence, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    confirmed: bool = False

    def confirm(self) -> "MemoryBootstrapProposal":
        return replace(self, confirmed=True)


@dataclass(frozen=True, slots=True)
class RepositoryBootstrapAnalyzer:
    """Conservative proposal engine for first-time project memory."""

    def enrich(self, project_root: Path, memory: ProjectMemory) -> tuple[ProjectMemory, tuple[BootstrapEvidence, ...]]:
        root = project_root.resolve()
        commands, command_evidence = self._commands(root, memory.modules)
        dependencies, dependency_evidence = self._dependencies(root, memory.modules)
        priorities = self._priorities(memory)
        priority_evidence = tuple(
            BootstrapEvidence(
                target="non-functional-priority",
                reason=f"proposed priority: {priority}",
                source="project type and detected technologies",
            )
            for priority in priorities
        )
        return (
            replace(
                memory,
                confirmed_check_commands=commands,
                dependencies=MappingProxyType(dependencies),
                non_functional_priorities=priorities,
            ),
            command_evidence + dependency_evidence + priority_evidence,
        )

    def _commands(
        self,
        root: Path,
        modules: tuple[ModuleMemory, ...],
    ) -> tuple[tuple[ConfirmedCommand, ...], tuple[BootstrapEvidence, ...]]:
        commands: list[ConfirmedCommand] = []
        evidence: list[BootstrapEvidence] = []
        seen: set[tuple[str, tuple[str, ...], str | None]] = set()

        def add(category: str, argv: tuple[str, ...], path: Path, *, required: bool = True) -> None:
            scope = _module_for_path(root, path, modules)
            key = (category, argv, scope)
            if key in seen:
                return
            seen.add(key)
            commands.append(
                ConfirmedCommand(
                    category=category,
                    command=argv,
                    scope=scope,
                    required=required,
                    global_check=scope is None,
                )
            )
            evidence.append(
                BootstrapEvidence(
                    target=f"command:{category}",
                    reason="repository declares a runnable verification script",
                    source=path.relative_to(root).as_posix(),
                )
            )

        for package in _package_json_files(root):
            try:
                data = json.loads(package.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            scripts = data.get("scripts", {})
            if not isinstance(scripts, dict):
                continue
            package_manager = _package_manager(package.parent, root)
            for category in _SCRIPT_CATEGORIES:
                if isinstance(scripts.get(category), str):
                    add(category, (package_manager, "run", category), package)

        solution = next(iter(sorted(root.glob("*.sln"))), None)
        if solution is not None:
            add("build", ("dotnet", "build", solution.name), solution)
            add("test", ("dotnet", "test", solution.name), solution)
        else:
            projects = tuple(sorted(root.rglob("*.csproj")))
            if len(projects) == 1:
                relative = projects[0].relative_to(root).as_posix()
                add("build", ("dotnet", "build", relative), projects[0])
                add("test", ("dotnet", "test", relative), projects[0])

        tests_dir = root / "tests"
        pyproject = root / "pyproject.toml"
        if tests_dir.is_dir() and pyproject.exists():
            pytest_declared = False
            try:
                with pyproject.open("rb") as handle:
                    data = tomllib.load(handle)
                tool = data.get("tool", {})
                pytest_declared = isinstance(tool, dict) and "pytest" in tool
            except (OSError, tomllib.TOMLDecodeError):
                pass
            if pytest_declared:
                add("test", ("python", "-m", "pytest"), pyproject)
            elif any(tests_dir.glob("test*.py")):
                add("test", ("python", "-m", "unittest", "discover", "-s", "tests", "-v"), pyproject)

        return tuple(commands), tuple(evidence)

    def _dependencies(
        self,
        root: Path,
        modules: tuple[ModuleMemory, ...],
    ) -> tuple[dict[str, tuple[str, ...]], tuple[BootstrapEvidence, ...]]:
        values: dict[str, set[str]] = {module.name: set() for module in modules}
        evidence: list[BootstrapEvidence] = []
        package_names: dict[str, str] = {}

        for module in modules:
            module_root = _module_root(root, module)
            if module_root is None:
                continue
            package = module_root / "package.json"
            if package.exists():
                try:
                    data = json.loads(package.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    data = {}
                name = data.get("name") if isinstance(data, dict) else None
                if isinstance(name, str) and name.strip():
                    package_names[name] = module.name

        for module in modules:
            module_root = _module_root(root, module)
            if module_root is None:
                continue
            package = module_root / "package.json"
            if package.exists() and package_names:
                try:
                    data = json.loads(package.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    data = {}
                for field_name in ("dependencies", "devDependencies", "peerDependencies"):
                    deps = data.get(field_name, {}) if isinstance(data, dict) else {}
                    if not isinstance(deps, dict):
                        continue
                    for package_name in deps:
                        target = package_names.get(package_name)
                        if target and target != module.name:
                            values[module.name].add(target)
                            evidence.append(
                                BootstrapEvidence(
                                    target=f"dependency:{module.name}->{target}",
                                    reason=f"package reference in {field_name}",
                                    source=package.relative_to(root).as_posix(),
                                )
                            )

            for project in module_root.rglob("*.csproj"):
                try:
                    xml_root = ET.parse(project).getroot()
                except (OSError, ET.ParseError):
                    continue
                for ref in xml_root.iter():
                    if not ref.tag.endswith("ProjectReference"):
                        continue
                    include = ref.attrib.get("Include")
                    if not include:
                        continue
                    target_path = (project.parent / include).resolve()
                    target = _module_for_path(root, target_path, modules)
                    if target and target != module.name:
                        values[module.name].add(target)
                        evidence.append(
                            BootstrapEvidence(
                                target=f"dependency:{module.name}->{target}",
                                reason=".NET ProjectReference",
                                source=project.relative_to(root).as_posix(),
                            )
                        )

            python_names = {candidate.name.replace("-", "_"): candidate.name for candidate in modules}
            for source in module_root.rglob("*.py"):
                if any(part.startswith(".") or part in {"venv", ".venv", "__pycache__"} for part in source.parts):
                    continue
                try:
                    text = source.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for imported in _IMPORT_RE.findall(text):
                    target = python_names.get(imported)
                    if target and target != module.name:
                        values[module.name].add(target)
                        evidence.append(
                            BootstrapEvidence(
                                target=f"dependency:{module.name}->{target}",
                                reason="Python import between detected modules",
                                source=source.relative_to(root).as_posix(),
                            )
                        )

        compact = {
            name: tuple(sorted(targets))
            for name, targets in values.items()
            if targets
        }
        unique_evidence = tuple(dict.fromkeys(evidence))
        return compact, unique_evidence

    @staticmethod
    def _priorities(memory: ProjectMemory) -> tuple[str, ...]:
        values = ["maintainability", "security", "testability"]
        if memory.metadata and memory.metadata.project_kind is ProjectKind.ACTIVE:
            values.append("reliability")
        return tuple(values)


@dataclass(frozen=True, slots=True)
class MemoryBootstrapService:
    initializer: MemoryInitializer
    analyzer: RepositoryBootstrapAnalyzer = RepositoryBootstrapAnalyzer()

    def propose(
        self,
        project_root: Path,
        *,
        project_name: str,
        reviewed_commit: str,
        purpose: str = "",
        project_kind: ProjectKind | None = None,
    ) -> MemoryBootstrapProposal:
        root = project_root.resolve()
        base = self.initializer.propose(
            root,
            project_name=project_name,
            reviewed_commit=reviewed_commit,
            purpose=purpose,
        )
        memory = base.memory
        if project_kind is not None and memory.metadata is not None:
            memory = replace(memory, metadata=replace(memory.metadata, project_kind=project_kind))
        memory, evidence = self.analyzer.enrich(root, memory)
        config = project_config_for(memory)
        target = root / ".factoria" / "config.toml"
        write_config = not target.exists()
        warnings: list[str] = []
        if not write_config:
            warnings.append(
                ".factoria/config.toml already exists; memoria-init will preserve it instead of overwriting it"
            )
        return MemoryBootstrapProposal(
            memory=memory,
            activity=base.activity,
            project_config=config,
            config_text=render_project_config(config),
            config_target=target,
            write_config=write_config,
            evidence=evidence,
            warnings=tuple(warnings),
        )

    def apply(self, project_root: Path, proposal: MemoryBootstrapProposal) -> tuple[Path, ...]:
        if not proposal.confirmed:
            raise PermissionError("Memory bootstrap must be confirmed before writing project files")
        root = project_root.resolve()
        existing_memory = [path for path in memory_targets(root, proposal.memory) if path.exists()]
        if existing_memory:
            joined = ", ".join(path.relative_to(root).as_posix() for path in existing_memory)
            raise FileExistsError(f"Initial memory would overwrite existing files: {joined}")

        written_memory = write_initial_memory(root, proposal.memory)
        written = [item.path for item in written_memory]
        if proposal.write_config:
            proposal.config_target.parent.mkdir(parents=True, exist_ok=True)
            proposal.config_target.write_text(proposal.config_text, encoding="utf-8", newline="")
            written.append(proposal.config_target)
        return tuple(written)


def project_config_for(memory: ProjectMemory) -> ProjectConfig:
    kind = memory.metadata.project_kind if memory.metadata else ProjectKind.MAINTENANCE
    thresholds = MappingProxyType(
        {document: _STALENESS_DEFAULT for document in MemoryDocumentKind}
    )
    return ProjectConfig(
        profile=None,
        max_agents=None,
        allowed_flows=(),
        blocked_flows=(),
        blocked_actions=(),
        memory=MemoryConfig(project_kind=kind, stale_after_commits=thresholds),
    )


def render_project_config(config: ProjectConfig) -> str:
    lines = [
        _PROJECT_CONFIG_MARKER,
        "",
        "[flows]",
        "allowed = []",
        "blocked = []",
        "",
        "[permissions]",
        "blocked_actions = []",
        "",
        "[memory]",
    ]
    if config.memory.project_kind is not None:
        lines.append(f'type = "{config.memory.project_kind.value}"')
    lines.extend(["", "[memory.staleness]"])
    for document in MemoryDocumentKind:
        threshold = config.memory.stale_after_commits.get(document, _STALENESS_DEFAULT)
        lines.append(f"{document.value} = {threshold}")
    lines.append("")
    return "\n".join(lines)


def _package_json_files(root: Path) -> tuple[Path, ...]:
    result: list[Path] = []
    for path in root.rglob("package.json"):
        if any(part in {"node_modules", ".git", ".factoria"} for part in path.parts):
            continue
        result.append(path)
    return tuple(sorted(result))


def _package_manager(directory: Path, root: Path) -> str:
    current = directory.resolve()
    root = root.resolve()
    while True:
        if (current / "pnpm-lock.yaml").exists():
            return "pnpm"
        if (current / "yarn.lock").exists():
            return "yarn"
        if (current / "package-lock.json").exists():
            return "npm"
        if current == root or root not in current.parents:
            break
        current = current.parent
    return "npm"


def _module_root(root: Path, module: ModuleMemory) -> Path | None:
    if not module.paths:
        return None
    candidate = (root / module.paths[0]).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate if candidate.exists() else None


def _module_for_path(root: Path, path: Path, modules: tuple[ModuleMemory, ...]) -> str | None:
    resolved = path.resolve()
    matches: list[tuple[int, str]] = []
    for module in modules:
        for raw in module.paths:
            module_path = (root / raw).resolve()
            try:
                resolved.relative_to(module_path)
            except ValueError:
                continue
            matches.append((len(module_path.parts), module.name))
    if not matches:
        return None
    return max(matches)[1]

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from factoria.adapters import CodexAdapter, OpenCodeAdapter, ToolAdapter
from factoria.config.loader import load_global_config, load_organization_config, load_project_config, resolve_config
from factoria.memory.git_staleness import GitMemoryStalenessInspector
from factoria.memory.loader import load_project_memory
from factoria.security import SecretScanner
from factoria.versioning import SemVer, VersionError

from .artifacts import FlowArtifactStore
from .history import HistoryRecord, LocalExecutionHistoryStore
from .impact import ImpactAnalyzer
from .runtime_state import RuntimeStateError, load_live_session
from .state_store import LocalFlowStateStore


@dataclass(frozen=True, slots=True)
class ToolStatus:
    name: str
    available: bool
    capabilities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FlowStatus:
    flow_id: str
    kind: str
    state: str
    runtime_stage: str | None
    branch: str | None
    label: str | None
    blocked: bool


@dataclass(frozen=True, slots=True)
class SecurityStatus:
    finding_count: int = 0
    summaries: tuple[str, ...] = field(default_factory=tuple)

    @property
    def blocked(self) -> bool:
        return self.finding_count > 0


@dataclass(frozen=True, slots=True)
class OperationalStatus:
    project_name: str
    branch: str
    dirty: bool
    project_kind: str | None
    memory_initialized: bool
    memory_commits_since_review: int | None
    stale_documents: tuple[str, ...]
    memory_version: str | None
    memory_version_warning: str | None
    effective_profile: str
    effective_tool: str | None
    max_agents: int
    blocked_actions: tuple[str, ...]
    organization_blocked_actions: tuple[str, ...]
    allowed_flows: tuple[str, ...]
    blocked_flows: tuple[str, ...]
    tools: tuple[ToolStatus, ...]
    active_flows: tuple[FlowStatus, ...]
    recent_results: tuple[HistoryRecord, ...]
    security: SecurityStatus
    warnings: tuple[str, ...]
    recommendations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OperationalStatusService:
    adapters: tuple[ToolAdapter, ...] = field(
        default_factory=lambda: (CodexAdapter(), OpenCodeAdapter())
    )
    secret_scanner: SecretScanner = SecretScanner()

    def inspect(self, project_root: Path, *, include_history: bool = False) -> OperationalStatus:
        root = project_root.expanduser().resolve()
        branch = _git(root, "branch", "--show-current").strip() or "(detached)"
        changed_paths = self.secret_scanner.changed_paths(root)
        dirty = bool(changed_paths)

        global_config = load_global_config(Path.home() / ".factoria" / "config.toml")
        organization = load_organization_config(Path.home() / ".factoria" / "organization.toml")
        project_config = load_project_config(root / ".factoria" / "config.toml")
        resolved = resolve_config(global_config, project_config)

        warnings: list[str] = []
        recommendations: list[str] = []
        project_kind: str | None = None
        memory_initialized = (root / "AGENTS.md").exists()
        memory_commits: int | None = None
        stale_documents: tuple[str, ...] = ()
        memory_version: str | None = None
        memory_version_warning: str | None = None

        if memory_initialized:
            try:
                memory = load_project_memory(root)
                impact = ImpactAnalyzer().analyze(memory, changed_paths)
                if impact.contract_impacts:
                    warnings.append(
                        "Modified files touch declared contract(s): "
                        + ", ".join(item.name for item in impact.contract_impacts)
                    )
                if impact.blocking:
                    warnings.append(
                        "External contract impact requires manual consumer/repository review before closure."
                    )
                    recommendations.append(
                        "Review the declared external consumers before confirming `factoria commit --confirm-external-impact-review`."
                    )
                if memory.metadata is not None:
                    project_kind = memory.metadata.project_kind.value
                    memory_version = memory.metadata.factoria_version
                    staleness = GitMemoryStalenessInspector().inspect(
                        root,
                        memory,
                        threshold_overrides=project_config.memory.stale_after_commits,
                    )
                    memory_commits = staleness.commits_since_review
                    stale_documents = tuple(item.value for item in staleness.stale_documents)
                    if stale_documents:
                        warnings.append("Project memory may be stale: " + ", ".join(stale_documents))
                        recommendations.append("Run `factoria memoria-update` and review the proposal.")
                    memory_version_warning = _memory_version_warning(memory_version)
                    if memory_version_warning:
                        warnings.append(memory_version_warning)
            except (FileNotFoundError, ValueError) as exc:
                warnings.append(f"Project memory could not be fully inspected: {exc}")
                recommendations.append("Review project memory before starting a new flow.")
        else:
            warnings.append("Project memory is not initialized.")
            recommendations.append("Run `factoria memoria-init` and review the proposal.")

        tools = tuple(
            ToolStatus(
                name=adapter.name,
                available=adapter.available(),
                capabilities=tuple(sorted(item.value for item in adapter.capabilities())),
            )
            for adapter in self.adapters
        )
        available_names = {item.name for item in tools if item.available}
        if resolved.tool is None:
            warnings.append("No default coding-agent tool is configured.")
            recommendations.append("Select a platform preference; start and authenticate Codex/OpenCode outside the application.")
        elif resolved.tool not in available_names:
            warnings.append(f"Configured tool {resolved.tool!r} is not currently available.")
            recommendations.append("Start the configured tool outside the application and check its installation there.")

        artifacts = FlowArtifactStore(root)
        state_store = LocalFlowStateStore(artifacts)
        active_flows: list[FlowStatus] = []
        for execution in state_store.incomplete():
            runtime_stage: str | None = None
            flow_branch: str | None = None
            session_path = execution.workspace.root / "agent-flow.json"
            if session_path.exists():
                try:
                    session = load_live_session(session_path, execution=execution)
                    runtime_stage = session.runtime_stage.value if session.runtime_stage else None
                    flow_branch = session.branch
                except (OSError, RuntimeStateError, FileNotFoundError) as exc:
                    warnings.append(
                        f"Flow {execution.flow.flow_id} has inconsistent live session metadata: {exc}"
                    )
            blocked = execution.flow.state.value == "blocked"
            active_flows.append(
                FlowStatus(
                    flow_id=execution.flow.flow_id,
                    kind=execution.flow.kind,
                    state=execution.flow.state.value,
                    runtime_stage=runtime_stage,
                    branch=flow_branch,
                    label=execution.label,
                    blocked=blocked,
                )
            )
            if blocked:
                warnings.append(f"Flow {execution.flow.flow_id} is blocked.")
                recommendations.append(
                    f"Inspect `.factoria/work/{execution.flow.flow_id}` before resuming the flow."
                )

        history = LocalExecutionHistoryStore(root).list(limit=10 if include_history else 5)

        secret_findings = self.secret_scanner.scan_files(root, changed_paths)
        security_summaries = tuple(
            f"{item.secret_type.value}@{item.location} fingerprint={item.fingerprint}"
            for item in secret_findings
        )
        security = SecurityStatus(
            finding_count=len(secret_findings),
            summaries=security_summaries,
        )
        if security.blocked:
            warnings.append(
                f"Security gate: {security.finding_count} potential secret(s) found in modified files."
            )
            recommendations.append(
                "Remove the secret material; if it was real, rotate/revoke it outside Factoria before continuing."
            )

        return OperationalStatus(
            project_name=root.name,
            branch=branch,
            dirty=dirty,
            project_kind=project_kind or (
                project_config.memory.project_kind.value
                if project_config.memory.project_kind is not None
                else None
            ),
            memory_initialized=memory_initialized,
            memory_commits_since_review=memory_commits,
            stale_documents=stale_documents,
            memory_version=memory_version,
            memory_version_warning=memory_version_warning,
            effective_profile=resolved.profile.value,
            effective_tool=resolved.tool,
            max_agents=resolved.max_agents,
            blocked_actions=resolved.blocked_actions,
            organization_blocked_actions=organization.blocked_actions,
            allowed_flows=resolved.allowed_flows,
            blocked_flows=resolved.blocked_flows,
            tools=tools,
            active_flows=tuple(active_flows),
            recent_results=history,
            security=security,
            warnings=tuple(dict.fromkeys(warnings)),
            recommendations=tuple(dict.fromkeys(recommendations)),
        )


def _installed_version() -> str | None:
    try:
        return version("factoria")
    except PackageNotFoundError:
        return None


def _memory_version_warning(memory_version: str) -> str | None:
    current = _installed_version()
    if current is None:
        return None
    try:
        memory = SemVer.parse(memory_version)
        installed = SemVer.parse(current)
    except VersionError:
        return None
    if memory.major != installed.major:
        return (
            f"Project memory was reviewed with Factoria {memory}; installed version is {installed} "
            "(major version differs)."
        )
    if memory.minor != installed.minor:
        return (
            f"Project memory was reviewed with Factoria {memory}; installed version is {installed} "
            "(minor version differs)."
        )
    return None


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from factoria.domain.models import ContractMemory, ModuleMemory, ProjectMemory


@dataclass(frozen=True, slots=True)
class ImpactItem:
    kind: str
    name: str
    confidence: str
    evidence: str


@dataclass(frozen=True, slots=True)
class ImpactReport:
    changed_paths: tuple[str, ...]
    items: tuple[ImpactItem, ...] = field(default_factory=tuple)
    blocking: bool = False

    @property
    def external_impacts(self) -> tuple[ImpactItem, ...]:
        return tuple(item for item in self.items if item.kind == "external")

    @property
    def contract_impacts(self) -> tuple[ImpactItem, ...]:
        return tuple(item for item in self.items if item.kind == "contract")


@dataclass(frozen=True, slots=True)
class ImpactAnalyzer:
    def analyze(self, memory: ProjectMemory, changed_paths: tuple[str, ...]) -> ImpactReport:
        normalized = tuple(self._normalize(path) for path in changed_paths)
        items: list[ImpactItem] = []

        direct_modules = {
            module.name
            for module in memory.modules
            if any(self._matches_any(path, module.paths) for path in normalized)
        }
        for name in sorted(direct_modules):
            items.append(ImpactItem("module", name, "confirmed", "changed path belongs to module"))

        inferred_modules = self._transitive_modules(memory.modules, direct_modules) - direct_modules
        for name in sorted(inferred_modules):
            items.append(
                ImpactItem(
                    "module",
                    name,
                    "inferred",
                    "declared module impact is reachable from a directly changed module",
                )
            )

        external_by_name = {item.name: item for item in memory.external_dependencies}
        touched_contracts: list[ContractMemory] = []
        for contract in memory.contracts:
            matched = tuple(path for path in normalized if self._matches_any(path, contract.paths))
            if not matched:
                continue
            touched_contracts.append(contract)
            items.append(
                ImpactItem(
                    "contract",
                    contract.name,
                    "confirmed",
                    "contract path changed: " + ", ".join(matched),
                )
            )
            for module in contract.affects_modules:
                items.append(
                    ImpactItem(
                        "module",
                        module,
                        "confirmed",
                        f"declared consumer of contract {contract.name}",
                    )
                )
            for external_name in contract.affects_external:
                dependency = external_by_name.get(external_name)
                evidence = f"declared external consumer of contract {contract.name}"
                if dependency is not None:
                    evidence += f" ({dependency.repository})"
                items.append(ImpactItem("external", external_name, "confirmed", evidence))

        deduped: dict[tuple[str, str, str], ImpactItem] = {}
        for item in items:
            deduped[(item.kind, item.name, item.evidence)] = item
        result = tuple(deduped.values())
        blocking = bool(touched_contracts and any(item.kind == "external" for item in result))
        return ImpactReport(changed_paths=changed_paths, items=result, blocking=blocking)

    @staticmethod
    def render(report: ImpactReport) -> str:
        lines = ["# Impact analysis", ""]
        if not report.items:
            lines.append("- No declared module, contract or external dependency impact detected.")
        else:
            for item in report.items:
                lines.append(
                    f"- {item.kind}: {item.name} | confidence={item.confidence} | {item.evidence}"
                )
        lines.extend(
            [
                "",
                f"blocking_external_review: {str(report.blocking).lower()}",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _normalize(path: str) -> str:
        return str(PurePosixPath(path.replace("\\", "/")))

    @classmethod
    def _matches_any(cls, path: str, roots: tuple[str, ...]) -> bool:
        for raw in roots:
            root = cls._normalize(raw).rstrip("/")
            if path == root or path.startswith(root + "/"):
                return True
        return False

    @staticmethod
    def _transitive_modules(modules: tuple[ModuleMemory, ...], direct: set[str]) -> set[str]:
        by_name = {item.name: item for item in modules}
        result = set(direct)
        pending = list(direct)
        while pending:
            current = pending.pop()
            module = by_name.get(current)
            if module is None:
                continue
            for target in module.affects:
                if target not in result:
                    result.add(target)
                    pending.append(target)
        return result

from __future__ import annotations

import shlex

from factoria.domain.models import MemoryDocumentKind, ProjectKind, ProjectMemory


def _metadata_header(memory: ProjectMemory) -> str:
    metadata = memory.metadata
    if metadata is None:
        return "<!-- factoria-memory: unreviewed -->"
    return (
        "<!-- factoria-memory: "
        f"type={metadata.project_kind.value} | "
        f"reviewed_commit={metadata.reviewed_commit} | "
        f"date={metadata.reviewed_at.isoformat()} | "
        f"factoria={metadata.factoria_version} -->"
    )


def _bullet_list(values: tuple[str, ...], *, empty: str = "- Sin datos confirmados") -> str:
    if not values:
        return empty
    return "\n".join(f"- {value}" for value in values)


def _render_commands(memory: ProjectMemory) -> list[str]:
    lines: list[str] = []
    if memory.confirmed_check_commands:
        for item in memory.confirmed_check_commands:
            scope = item.scope or "global"
            requirement = "obligatorio" if item.required else "opcional"
            global_marker = ", global" if item.global_check else ""
            lines.append(
                f"- **{item.category} / {scope}** ({requirement}{global_marker}): "
                f"{shlex.join(item.command)}"
            )
        return lines

    for category, commands in memory.confirmed_commands.items():
        rendered = [shlex.join(command) for command in commands]
        lines.append(f"- **{category}**: {'; '.join(rendered)}")
    return lines


def _render_contracts(memory: ProjectMemory) -> list[str]:
    lines: list[str] = []
    for item in memory.contracts:
        modules = ", ".join(item.affects_modules) or "-"
        external = ", ".join(item.affects_external) or "-"
        lines.append(
            f"- **{item.name}**: paths={', '.join(item.paths)}; "
            f"modules={modules}; external={external}"
        )
    return lines


def _render_external_dependencies(memory: ProjectMemory) -> list[str]:
    lines: list[str] = []
    for item in memory.external_dependencies:
        relationship = item.relationship or "unspecified"
        lines.append(
            f"- **{item.name}**: repository={item.repository}; relationship={relationship}"
        )
    return lines


def render_agents_md(memory: ProjectMemory) -> str:
    lines: list[str] = [
        _metadata_header(memory),
        f"# {memory.project_name}",
        "",
        "## Propósito",
        memory.purpose or "Pendiente de confirmar.",
        "",
        "## Tecnologías",
        _bullet_list(memory.technologies),
        "",
        "## Módulos",
    ]

    if memory.modules:
        for module in memory.modules:
            paths = ", ".join(module.paths) or "sin rutas confirmadas"
            lines.append(f"- **{module.name}**: {paths}")
    else:
        lines.append("- Sin módulos confirmados")

    lines.extend(["", "## Comandos confirmados"])
    rendered_commands = _render_commands(memory)
    lines.extend(rendered_commands or ["- Ninguno confirmado todavía"])

    lines.extend(["", "## Reglas obligatorias", _bullet_list(memory.mandatory_rules)])
    lines.extend(
        ["", "## Prioridades no funcionales", _bullet_list(memory.non_functional_priorities)]
    )
    lines.extend(["", "## Dependencias"])
    if memory.dependencies:
        for source, targets in memory.dependencies.items():
            lines.append(f"- **{source}** → {', '.join(targets)}")
    else:
        lines.append("- Sin dependencias confirmadas")

    lines.extend(["", "## Contratos"])
    lines.extend(_render_contracts(memory) or ["- Sin contratos confirmados"])
    lines.extend(["", "## Dependencias externas"])
    lines.extend(
        _render_external_dependencies(memory) or ["- Sin dependencias externas confirmadas"]
    )

    if memory.metadata and memory.metadata.project_kind is ProjectKind.ACTIVE:
        lines.extend(
            [
                "",
                "## Memoria detallada",
                "- Arquitectura: `docs/memoria/arquitectura.md`",
                "- Flujos: `docs/memoria/flujos.md`",
                "- Decisiones: `docs/memoria/decisiones.md`",
                "- Verificación: `docs/memoria/testing.md`",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Memoria detallada",
                "Proyecto de mantenimiento: consultar `docs/memoria/testing.md` cuando sea necesario.",
            ]
        )

    lines.extend(
        [
            "",
            "## Uso por agentes",
            "Consulta primero este archivo. Abre solo la memoria detallada relevante para la tarea.",
            "Si el código contradice comportamiento o estructura descritos aquí, marca la memoria como potencialmente desactualizada.",
            "Las reglas obligatorias no se ignoran automáticamente aunque el código actual las contradiga.",
            "",
        ]
    )
    return "\n".join(lines)


def render_memory_document(memory: ProjectMemory, document: MemoryDocumentKind) -> str:
    title = {
        MemoryDocumentKind.ARCHITECTURE: "Arquitectura",
        MemoryDocumentKind.FLOWS: "Flujos",
        MemoryDocumentKind.DECISIONS: "Decisiones",
        MemoryDocumentKind.TESTING: "Verificación y pruebas",
    }[document]

    lines = [_metadata_header(memory), f"# {title}", ""]

    if document is MemoryDocumentKind.ARCHITECTURE:
        lines.append("## Módulos")
        if memory.modules:
            for module in memory.modules:
                paths = ", ".join(module.paths) or "sin rutas confirmadas"
                affects = f"; afecta a: {', '.join(module.affects)}" if module.affects else ""
                lines.append(f"- **{module.name}**: {paths}{affects}")
        else:
            lines.append("- Pendiente de documentar")
        lines.extend(["", "## Dependencias"])
        if memory.dependencies:
            for source, targets in memory.dependencies.items():
                lines.append(f"- **{source}** → {', '.join(targets)}")
        else:
            lines.append("- Pendiente de documentar")
        lines.extend(["", "## Contratos"])
        lines.extend(_render_contracts(memory) or ["- Sin contratos confirmados"])
        lines.extend(["", "## Dependencias externas"])
        lines.extend(
            _render_external_dependencies(memory) or ["- Sin dependencias externas confirmadas"]
        )
        lines.extend(
            ["", "## Prioridades no funcionales", _bullet_list(memory.non_functional_priorities)]
        )

    elif document is MemoryDocumentKind.FLOWS:
        lines.extend(
            [
                "Documenta únicamente los flujos relevantes y estables del proyecto.",
                "No incluir detalles efímeros de implementación.",
            ]
        )

    elif document is MemoryDocumentKind.DECISIONS:
        lines.append(_bullet_list(memory.decisions, empty="- Sin decisiones registradas"))

    elif document is MemoryDocumentKind.TESTING:
        lines.extend(["## Estado", ""])
        rendered_commands = _render_commands(memory)
        lines.extend(rendered_commands or ["- No hay comandos de verificación confirmados"])
        lines.extend(["", "## Cómo comprobarlo a mano", _bullet_list(memory.manual_verification)])

    lines.append("")
    return "\n".join(lines)

"""Validate the saved visual diagram independently of executable steps."""

import re
from graphlib import CycleError, TopologicalSorter

from factoria.security import SecretScanner


def validate_diagram(raw: object, stages: set[str]) -> dict | None:
    if raw is None:
        return None
    if (
        not isinstance(raw, dict)
        or set(raw) - {"nodes", "edges", "execute"}
        or not {"nodes", "edges"} <= raw.keys()
        or not isinstance(raw.get("execute", False), bool)
    ):
        raise ValueError("El diagrama necesita nodos y conexiones")
    nodes, edges = raw["nodes"], raw["edges"]
    if not isinstance(nodes, dict) or len(stages | nodes.keys()) > 1000:
        raise ValueError("El diagrama admite hasta 1000 nodos")
    if not isinstance(edges, list) or len(edges) > 4000:
        raise ValueError("El diagrama admite hasta 4000 conexiones")
    labels = []
    for key, node in nodes.items():
        if not isinstance(key, str) or not isinstance(node, dict):
            raise ValueError("Nodo de diagrama no válido")
        stage = key in stages
        if not stage and not re.fullmatch(r"note-[a-z0-9-]{1,48}", key):
            raise ValueError("Identificador de nodo no válido")
        if set(node) != ({"x", "y"} if stage else {"x", "y", "label"}):
            raise ValueError("Campos de nodo no válidos")
        if any(type(node[axis]) is not int or not 0 <= node[axis] <= 50000 for axis in ("x", "y")):
            raise ValueError("Posición de nodo fuera del lienzo")
        if not stage:
            label = node["label"]
            if not isinstance(label, str) or not label.strip() or len(label) > 120:
                raise ValueError("Cada caja de análisis necesita un nombre de hasta 120 caracteres")
            labels.append(label)
    if labels and SecretScanner().scan_text("\n".join(labels), location="workflow-diagram"):
        raise ValueError("Posible secreto en el diagrama")
    known = stages | nodes.keys()
    seen = set()
    for edge in edges:
        if (
            not isinstance(edge, list)
            or len(edge) != 2
            or any(not isinstance(end, str) or end not in known for end in edge)
            or edge[0] == edge[1]
            or tuple(edge) in seen
        ):
            raise ValueError("Conexión de diagrama no válida o duplicada")
        seen.add(tuple(edge))
    return raw


def execution_route(diagram: dict | None, stages: list[str]) -> list[str]:
    """Compile a directed graph into the order of ready tasks for a single session."""
    if not diagram or not diagram.get("execute"):
        return stages

    nodes = [*stages, *sorted(
        key for key, node in diagram["nodes"].items() if "label" in node
    )]
    dependencies: dict[str, set[str]] = {key: set() for key in nodes}
    for source, target in diagram["edges"]:
        if source not in dependencies or target not in dependencies:
            raise ValueError("Conecta solo cajas activas para ejecutar la ruta")
        dependencies[target].add(source)
    sorter = TopologicalSorter({node: () for node in nodes})
    for node, parents in dependencies.items():
        sorter.add(node, *parents)
    try:
        order = list(sorter.static_order())
    except CycleError as exc:
        raise ValueError("La ruta contiene un ciclo. Quita una conexión para poder ejecutarla") from exc
    if [node for node in nodes if not dependencies[node]] != ["explore"]:
        raise ValueError("Todas las cajas activas deben estar conectadas a la ruta desde explore")

    stage_set = set(stages)
    preceding_stages: dict[str, set[str]] = {}
    for node in order:
        completed = set()
        for parent in dependencies[node]:
            completed.update(preceding_stages[parent])
            if parent in stage_set:
                completed.add(parent)
        preceding_stages[node] = completed
    for source, target in zip(stages, stages[1:]):
        if source not in preceding_stages[target]:
            raise ValueError(f"La ruta debe conectar {source} con {target} antes de continuar")
    return order

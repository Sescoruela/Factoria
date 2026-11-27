"""Convert public GitHub resource files into portable templates for review."""

import re
import tomllib
import unicodedata
from pathlib import PurePosixPath
from urllib.error import URLError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

from factoria.application.projects.project_templates import validate_template
from factoria.orchestration import AgentRole


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def github_resource_url(value: str) -> str:
    url = urlsplit(value)
    parts = unquote(url.path).split("/")[1:]
    if url.scheme != "https" or url.query or url.fragment:
        raise ValueError("Pega un enlace HTTPS directo a un archivo público de GitHub")
    if url.netloc == "github.com" and len(parts) >= 5 and parts[2] == "blob":
        parts.pop(2)
    elif url.netloc != "raw.githubusercontent.com":
        raise ValueError("El enlace debe apuntar a un archivo público de GitHub")
    if (
        len(parts) < 4
        or any(not part or part in (".", "..") for part in parts)
        or PurePosixPath(parts[-1]).suffix.lower() not in {".md", ".toml"}
    ):
        raise ValueError("Selecciona un archivo Markdown o TOML del repositorio")
    return "https://raw.githubusercontent.com/" + "/".join(quote(part, safe="") for part in parts)


def download_resource(value: str) -> tuple[str, str]:
    url = github_resource_url(value)
    try:
        with build_opener(_NoRedirect()).open(url, timeout=8) as response:
            raw = response.read(128 * 1024 + 1)
        if len(raw) > 128 * 1024:
            raise ValueError("El archivo supera 128 KiB")
        return unquote(url.rsplit("/", 1)[-1]), raw.decode("utf-8-sig")
    except (URLError, OSError, UnicodeError) as exc:
        raise ValueError("No se pudo leer el archivo público de GitHub en UTF-8") from exc


def resource_template(filename: str, text: str, kind: str, role: str, identifier: str) -> dict:
    if not all(isinstance(v, str) for v in (filename, text, kind, role, identifier)):
        raise ValueError("Datos del recurso no válidos")
    if kind not in {"skill", "agent"}:
        raise ValueError("Selecciona si el archivo es una skill o un agente")
    if len(text.encode("utf-8")) > 128 * 1024:
        raise ValueError("El archivo supera 128 KiB")
    file = PurePosixPath(filename)
    default_name = file.stem
    metadata = {}
    body = text
    if file.suffix.lower() == ".toml" and kind == "agent":
        metadata = tomllib.loads(text)
        body = metadata.get("developer_instructions", "")
    elif file.suffix.lower() == ".md":
        lines = text.splitlines(keepends=True)
        if lines and lines[0].strip() == "---":
            end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
            if end is None:
                raise ValueError("Cabecera Markdown sin cerrar")
            for line in lines[1:end]:
                match = re.fullmatch(r"(name|description):\s*(.+?)\s*", line)
                if match and match[2] not in {"|", ">", "|-", ">-", "|+", ">+"}:
                    metadata[match[1]] = match[2].strip("\"'")
            body = "".join(lines[end + 1 :])
        if default_name.lower() == "skill":
            heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            if heading:
                default_name = heading[1]
    else:
        raise ValueError("Usa Markdown para skills y Markdown o TOML para agentes")

    name = metadata.get("name") or default_name
    description = metadata.get("description") or ""
    if not all(isinstance(item, str) for item in (name, description, body)) or not body.strip():
        raise ValueError("El archivo necesita instrucciones de texto")
    letters = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", letters.lower()).strip("-")
    if not re.match(r"[a-z]", slug):
        slug = f"{kind}-{slug}".rstrip("-")
    identifier = identifier.strip() or slug[:64].rstrip("-")
    common = {"name": name, "description": description}
    skills, agents = [], []
    if kind == "skill":
        skills.append({**common, "id": identifier, "content": body})
    else:
        if role not in {item.value for item in AgentRole}:
            raise ValueError("Selecciona la función del agente")
        if identifier in {item.value for item in AgentRole}:
            raise ValueError("Elige un identificador distinto al de los agentes básicos")
        agents.append({
            **common, "role": identifier, "base_role": role, "profile": "equilibrado",
            "instructions": body,
        })
    return validate_template({
        "schema_version": 1, "name": name, "skills": skills, "agents": agents, "workflows": {},
    })

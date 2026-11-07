"""The main shell is canonical; the classic shell remains a compatibility view."""

from importlib.resources import files


def main_shell_html() -> str:
    return files("factoria.web").joinpath("index_n8n.html").read_text(encoding="utf-8")

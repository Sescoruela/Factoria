from __future__ import annotations

import unittest
from importlib.resources import files

from factoria.web.backend.server import FactoriaWebHandler
from factoria.web.backend.main_shell import FactoriaN8NHandler


class N8NWebUiTests(unittest.TestCase):
    def test_n8n_handler_reuses_governed_factoria_api(self) -> None:
        self.assertTrue(issubclass(FactoriaN8NHandler, FactoriaWebHandler))

    def test_n8n_shell_contains_canvas_nodes_and_connections(self) -> None:
        html = files("factoria.web.frontend").joinpath("index_n8n.html").read_text(encoding="utf-8")
        self.assertIn('id="workflowCanvas"', html)
        self.assertIn('id="connections"', html)
        assets = "".join(
            files("factoria.web.frontend").joinpath(name).read_text(encoding="utf-8")
            for name in ("agents.js", "shell-main.js", "workflow-canvas.js")
        )
        self.assertIn('class="port in"', assets)
        self.assertIn('class="port out"', assets)
        self.assertIn("startNodeDrag", assets)
        self.assertIn("drawConnections", assets)
        self.assertIn("/api/workflow/save", assets)

    def test_visual_shell_keeps_existing_product_sections(self) -> None:
        html = files("factoria.web.frontend").joinpath("index_n8n.html").read_text(encoding="utf-8")
        for section in (
            "dashboard",
            "projects",
            "agents",
            "designer",
            "flows",
            "history",
            "security",
            "commands",
        ):
            self.assertIn(f'id="{section}"', html)


if __name__ == "__main__":
    unittest.main()

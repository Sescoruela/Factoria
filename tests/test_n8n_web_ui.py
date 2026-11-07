from __future__ import annotations

import unittest
from importlib.resources import files

from factoria.web_app import FactoriaWebHandler
from factoria.web_app_n8n import FactoriaN8NHandler


class N8NWebUiTests(unittest.TestCase):
    def test_n8n_handler_reuses_governed_factoria_api(self) -> None:
        self.assertTrue(issubclass(FactoriaN8NHandler, FactoriaWebHandler))

    def test_n8n_shell_contains_canvas_nodes_and_connections(self) -> None:
        html = files("factoria.web").joinpath("index_n8n.html").read_text(encoding="utf-8")
        self.assertIn('id="workflowCanvas"', html)
        self.assertIn('id="connections"', html)
        assets = files("factoria.web").joinpath("agents.js").read_text(encoding="utf-8") + files("factoria.web").joinpath("shell-main.js").read_text(encoding="utf-8")
        self.assertIn('class="port in"', assets)
        self.assertIn('class="port out"', assets)
        self.assertIn("startNodeDrag", assets)
        self.assertIn("drawConnections", assets)
        self.assertIn("/api/workflow/save", assets)

    def test_visual_shell_keeps_existing_product_sections(self) -> None:
        html = files("factoria.web").joinpath("index_n8n.html").read_text(encoding="utf-8")
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

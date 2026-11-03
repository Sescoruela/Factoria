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
        self.assertIn('class="port in"', html)
        self.assertIn('class="port out"', html)
        self.assertIn("startNodeDrag", html)
        self.assertIn("drawConnections", html)
        self.assertIn("/api/workflow/save", html)

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

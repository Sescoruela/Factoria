from __future__ import annotations

import threading
import unittest
import urllib.error
import urllib.request
from importlib.resources import files

from factoria.web_app import FactoriaHTTPServer, FactoriaWebHandler, _run_factoria_command


class WebAssetTests(unittest.TestCase):
    def test_packaged_index_exists(self) -> None:
        html = files("factoria.web").joinpath("index.html").read_text(encoding="utf-8")
        self.assertIn("Factoria", html)
        self.assertIn("Resumen", html)
        self.assertIn("/assets/shell-classic.js", html)
        self.assertIn("/api/state", files("factoria.web").joinpath("shell-classic.js").read_text(encoding="utf-8"))

    def test_command_boundary_rejects_unknown_command(self) -> None:
        with self.assertRaises(ValueError):
            _run_factoria_command(["powershell", "whoami"], None)


class WebServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = FactoriaHTTPServer(("127.0.0.1", 0), FactoriaWebHandler)
        self.server.factoria_token = "test-token"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_index_is_public_but_api_requires_session_token(self) -> None:
        for route, asset in (("/", "index.html"), ("/editors", "index_n8n.html")):
            with self.subTest(route=route):
                expected = files("factoria.web").joinpath(asset).read_bytes()
                with urllib.request.urlopen(self.base + route, timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers["X-Frame-Options"], "DENY")
                    self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                    self.assertEqual(response.read(), expected)

        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.base + "/api/state", timeout=3)
        self.assertEqual(caught.exception.code, 403)

    def test_authorized_state_request(self) -> None:
        request = urllib.request.Request(
            self.base + "/api/state",
            headers={"X-Factoria-Token": "test-token"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"projects", response.read())


if __name__ == "__main__":
    unittest.main()

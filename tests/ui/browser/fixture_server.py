"""Disposable real-HTTP fixture for Playwright; never uses the user's HOME/projects."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
from unittest.mock import patch
from urllib.parse import urlparse

from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaHTTPServer, FactoriaWebHandler
from factoria.web_app_n8n import FactoriaN8NHandler

TOKEN = "disposable-browser-fixture"


def main() -> None:
    port = int(os.environ.get("FACTORIA_BROWSER_PORT", "8769"))
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    with tempfile.TemporaryDirectory(prefix="factoria-browser-") as temp:
        root = Path(temp).resolve()
        home = root / "home"
        home.mkdir()
        counter = 0
        fixture = {}

        def reset():
            nonlocal counter
            counter += 1
            base = root / f"case-{counter}"
            base.mkdir()
            for name in ("project", "other"):
                subprocess.run(
                    ["git", "init", "-b", "main", str(base / name)], check=True, capture_output=True
                )
            UiWorkspaceSettings(base, base / "project").save()
            fixture.update(
                project=str(base / "project"),
                other=str(base / "other"),
                url=f"http://127.0.0.1:{port}",
                classic_url=f"http://127.0.0.1:{port + 1}",
                token=TOKEN,
            )

        class TestEndpoints:
            def do_GET(self):
                if urlparse(self.path).path == "/__test__/fixture":
                    self._json(fixture)
                else:
                    super().do_GET()

            def do_POST(self):
                if urlparse(self.path).path == "/__test__/reset":
                    if not self._authorized():
                        self._json({"error": "unauthorized"}, 403)
                        return
                    data = self._body()
                    reset()
                    if data.get("selected") is False:
                        UiWorkspaceSettings(Path(fixture["project"]).parent, None).save()
                    self._json(fixture)
                else:
                    super().do_POST()

            def log_message(self, *_):
                pass

        class MainHandler(TestEndpoints, FactoriaN8NHandler):
            pass

        class ClassicHandler(TestEndpoints, FactoriaWebHandler):
            pass

        with patch("pathlib.Path.home", return_value=home):
            reset()
            servers = []
            threads = []
            try:
                for address, handler in ((port + 1, ClassicHandler), (port, MainHandler)):
                    server = FactoriaHTTPServer(("127.0.0.1", address), handler)
                    server.factoria_token = TOKEN
                    servers.append(server)
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    threads.append(thread)
                    thread.start()
                print(json.dumps({"ready": True, "url": fixture["url"]}), flush=True)
                stop.wait()
            finally:
                for server in servers:
                    server.shutdown()
                    server.server_close()
                for thread in threads:
                    thread.join(timeout=2)


if __name__ == "__main__":
    main()

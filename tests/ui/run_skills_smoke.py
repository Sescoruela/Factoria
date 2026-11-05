"""Optional DOM smoke runner: Node + jsdom must be available via NODE_PATH."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaHTTPServer, FactoriaWebHandler
from factoria.web_app_n8n import FactoriaN8NHandler


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='factoria-skills-ui-') as temp:
        base = Path(temp).resolve()
        home = base / 'home'
        home.mkdir()
        for name in ('project', 'other'):
            folder = base / name
            folder.mkdir()
            subprocess.run(['git', 'init', '-b', 'main', str(folder)], check=True, capture_output=True)
        with patch('pathlib.Path.home', return_value=home):
            UiWorkspaceSettings(base, base / 'project').save()
            server = FactoriaHTTPServer(('127.0.0.1', 0), FactoriaN8NHandler)
            server.factoria_token = 'ui-test-token'
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            legacy = FactoriaHTTPServer(('127.0.0.1', 0), FactoriaWebHandler)
            legacy.factoria_token = 'ui-test-token'
            legacy_thread = threading.Thread(target=legacy.serve_forever, daemon=True)
            legacy_thread.start()
            try:
                environment = os.environ.copy()
                environment['FACTORIA_SKILL_FIXTURE'] = json.dumps({
                    'project': str(base / 'project'), 'other': str(base / 'other'),
                    'url': f'http://127.0.0.1:{server.server_address[1]}',
                    'legacy_url': f'http://127.0.0.1:{legacy.server_address[1]}',
                })
                scenario = ('named_workflows_smoke.cjs' if '--named-workflows' in sys.argv else
                            'workflow_agents_smoke.cjs' if '--workflow-agents' in sys.argv else 'skills_smoke.cjs')
                return subprocess.run(['node', str(Path(__file__).with_name(scenario))],
                                      env=environment, timeout=45).returncode
            finally:
                legacy.shutdown()
                legacy.server_close()
                legacy_thread.join(timeout=2)
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == '__main__':
    sys.exit(main())

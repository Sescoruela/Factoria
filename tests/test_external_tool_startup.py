from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from factoria.application.tool_presence import assert_ui_command_allowed
from factoria.ui_agent_tools import AgentAwareTerminalUI
from factoria.ui_cli import TerminalUI
from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaHTTPServer, _agent_payload, _set_default_tool
from factoria.web_app_n8n import FactoriaN8NHandler


class ExternalToolStartupTests(unittest.TestCase):
    def test_repeated_platform_refresh_never_starts_a_process(self):
        with patch('subprocess.run', side_effect=AssertionError('Unexpected process startup')), patch('factoria.web_app._apply_agent_paths', return_value={}):
            for _ in range(4):
                payload = _agent_payload()
                self.assertEqual([p['name'] for p in payload], ['codex', 'opencode'])
                self.assertTrue(all(not p['ready'] and p['external_start'] for p in payload))

    def test_saving_preference_never_probes_provider_and_preserves_config(self):
        with tempfile.TemporaryDirectory() as temp, patch('pathlib.Path.home', return_value=Path(temp)), patch('subprocess.run', side_effect=AssertionError('No provider process')):
            first = _set_default_tool('codex')
            before = first.read_text()
            second = _set_default_tool('opencode')
            after = second.read_text()
            self.assertIn('default_tool = "opencode"', after)
            self.assertEqual(before.replace('"codex"', '"opencode"'), after)

    def test_console_cannot_bypass_external_start_with_global_options(self):
        for args in (['feature', 'x'], ['fix', 'x'], ['resume', 'flow'], ['install', '--check-only'],
                     ['--project', '.', 'fix', 'x'], ['--project=.', '--read-only', 'resume', 'x'],
                     ['--profile', 'normal', 'install'], ['--profile=normal', 'feature', 'x']):
            with self.subTest(args=args), self.assertRaisesRegex(ValueError, 'fuera'):
                assert_ui_command_allowed(args)

    def test_tui_command_boundary_never_dispatches_provider_start(self):
        with tempfile.TemporaryDirectory() as temp:
            ui = TerminalUI(Path(temp), output_fn=lambda _: None,
                            command_runner=lambda _: self.fail('No UI provider startup'))
            for command in ('feature', 'fix', 'resume', 'install'):
                self.assertEqual(ui._run_command([command]), 1)

    def test_passive_tui_dashboard_never_probes_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            ui = AgentAwareTerminalUI(Path(temp), output_fn=lambda _: None)
            with patch('factoria.ui_project_flow.ProjectFlowTerminalUI._render_dashboard'), patch('subprocess.run', side_effect=AssertionError('No process')):
                ui._render_dashboard()


class ExternalToolHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.home_patch = patch('pathlib.Path.home', return_value=self.home)
        self.home_patch.start()
        self.settings_patch = patch('factoria.ui_workspace.UiWorkspaceSettings.load', return_value=UiWorkspaceSettings())
        self.settings_patch.start()
        self.server = FactoriaHTTPServer(('127.0.0.1', 0), FactoriaN8NHandler)
        self.server.factoria_token = 'fixture-token'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.settings_patch.stop()
        self.home_patch.stop()
        self.temp.cleanup()

    def request(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, headers={'X-Factoria-Token': 'fixture-token', 'Content-Type': 'application/json'})
        return urllib.request.urlopen(req, timeout=3)

    def test_authenticated_refreshes_do_not_execute_cli(self):
        with patch('subprocess.run', side_effect=AssertionError('No provider probes')):
            for _ in range(3):
                with self.request('/api/state') as response:
                    state = json.load(response)
                    self.assertEqual(len(state['platforms']), 2)

    def test_launch_and_diagnostic_endpoints_are_blocked(self):
        with patch('subprocess.run', side_effect=AssertionError('No provider process')):
            for path, args in (('/api/job/start', ['feature', 'demo']), ('/api/job/start', ['fix', 'demo']),
                               ('/api/command', ['resume', 'flow']), ('/api/command', ['install', '--check-only'])):
                with self.subTest(path=path, args=args), self.assertRaises(urllib.error.HTTPError) as error:
                    self.request(path, {'args': args})
                self.assertEqual(error.exception.code, 400)


if __name__ == '__main__':
    unittest.main()

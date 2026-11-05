from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from factoria.application.workflow_presets import (
    WorkflowCatalogConflict, default_preset, load_preset, save_preset,
    workflow_catalog_revision, workflow_catalog_snapshot,
)
from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaHTTPServer, FactoriaWebHandler, _workflow_payload


def with_profile(preset, stage, profile):
    return replace(preset, steps=tuple(replace(s, profile=profile) if s.name == stage else s for s in preset.steps))


class WorkflowPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        home = patch('pathlib.Path.home', return_value=self.root / 'home')
        home.start()
        self.addCleanup(home.stop)

    def test_stale_editor_cannot_undo_another_edit(self):
        preset = default_preset('fix')
        revision = workflow_catalog_revision(self.root)
        path = save_preset(self.root, with_profile(preset, 'implement', 'potente'), expected_revision=revision)
        before = path.read_bytes()
        with self.assertRaises(WorkflowCatalogConflict):
            save_preset(self.root, with_profile(preset, 'review', 'rapido'), expected_revision=revision)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(next(s.profile for s in load_preset(self.root, 'fix').steps if s.name == 'implement'), 'potente')

    def test_concurrent_editors_get_one_success_and_one_conflict(self):
        revision = workflow_catalog_revision(self.root)
        barrier = threading.Barrier(2)
        def save(profile):
            barrier.wait(timeout=5)
            try:
                save_preset(self.root, with_profile(default_preset('fix'), 'implement', profile), expected_revision=revision)
                return 'saved'
            except WorkflowCatalogConflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(executor.map(save, ('potente', 'rapido')), ('saved', 'conflict'))

    def test_atomic_replace_failure_preserves_original_and_cleans_up(self):
        path = save_preset(self.root, default_preset('feature'))
        before = path.read_bytes()
        files = set(path.parent.iterdir())
        with patch('factoria.application.workflow_presets.os.replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                save_preset(self.root, with_profile(default_preset('feature'), 'implement', 'rapido'))
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(files, set(path.parent.iterdir()))

    def test_external_edit_during_write_is_preserved(self):
        path = save_preset(self.root, default_preset('fix'))
        external = path.read_text(encoding='utf-8') + '\n'
        real_fsync = os.fsync
        def external_edit(fd):
            real_fsync(fd)
            path.write_text(external, encoding='utf-8')
        with patch('factoria.application.workflow_presets.os.fsync', side_effect=external_edit):
            with self.assertRaises(WorkflowCatalogConflict):
                save_preset(self.root, with_profile(default_preset('fix'), 'implement', 'potente'))
        self.assertEqual(path.read_text(encoding='utf-8'), external)
        self.assertEqual([p.name for p in path.parent.iterdir()], ['workflows.json'])

    def test_legacy_migrates_and_other_workflow_is_preserved(self):
        folder = self.root / '.factoria'
        folder.mkdir()
        feature = with_profile(default_preset('feature'), 'review', 'rapido')
        (folder / 'ui-workflows.json').write_text(json.dumps({'feature': feature.to_mapping()}))
        presets, revision = workflow_catalog_snapshot(self.root)
        save_preset(self.root, presets['fix'], expected_revision=revision)
        self.assertEqual(load_preset(self.root, 'feature'), feature)
        payload = _workflow_payload(self.root)
        self.assertEqual(payload['fix']['revision'], payload['feature']['revision'])
        self.assertNotEqual(payload['fix']['revision'], revision)

    def test_invalid_existing_json_never_gets_replaced(self):
        folder = self.root / '.factoria'
        folder.mkdir()
        path = folder / 'workflows.json'
        path.write_text('{broken')
        with self.assertRaises(ValueError):
            save_preset(self.root, default_preset('fix'))
        self.assertEqual(path.read_text(), '{broken')
        self.assertIn('error', _workflow_payload(self.root)['fix'])

    @unittest.skipIf(os.name == 'nt', 'Windows symlink creation needs elevated privileges')
    def test_symlinked_source_cannot_be_read_or_overwritten(self):
        outside = self.root / 'outside.json'
        outside.write_text('{}')
        folder = self.root / '.factoria'
        folder.mkdir()
        (folder / 'workflows.json').symlink_to(outside)
        with self.assertRaises(ValueError):
            load_preset(self.root, 'fix')
        with self.assertRaises(ValueError):
            save_preset(self.root, default_preset('fix'))
        self.assertEqual(outside.read_text(), '{}')

    def test_api_requires_auth_revision_and_expected_project(self):
        (self.root / '.git').mkdir()
        UiWorkspaceSettings(self.root.parent, self.root).save()
        server = FactoriaHTTPServer(('127.0.0.1', 0), FactoriaWebHandler)
        server.factoria_token = 'test-token'
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def request(data, authorized=True):
                headers = {'Content-Type': 'application/json'}
                if authorized:
                    headers['X-Factoria-Token'] = 'test-token'
                req = urllib.request.Request(f'http://127.0.0.1:{server.server_address[1]}/api/workflow/save',
                                             data=json.dumps(data).encode(), headers=headers)
                with urllib.request.urlopen(req, timeout=3) as response:
                    return json.load(response)
            payload = {**default_preset('fix').to_mapping(), 'revision': workflow_catalog_revision(self.root), 'project_path': str(self.root)}
            with self.assertRaises(urllib.error.HTTPError) as caught:
                request(payload, False)
            self.assertEqual(caught.exception.code, 403)
            with patch('factoria.web_app._state', return_value={}):
                self.assertTrue(request(payload)['ok'])
                before = (self.root / '.factoria/workflows.json').read_bytes()
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request(payload)
                self.assertEqual(caught.exception.code, 409)
                payload['revision'] = workflow_catalog_revision(self.root)
                payload['project_path'] = str(self.root / 'another')
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request(payload)
                self.assertEqual(caught.exception.code, 409)
                payload['project_path'] = str(self.root)
                del payload['revision']
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request(payload)
                self.assertEqual(caught.exception.code, 400)
                self.assertEqual(before, (self.root / '.factoria/workflows.json').read_bytes())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

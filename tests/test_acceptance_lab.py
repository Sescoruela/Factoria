from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factoria.application.native_workflow import NativeWorkflow
from factoria.application.project_integration import ProjectIntegration

spec = importlib.util.spec_from_file_location('acceptance_lab', Path(__file__).resolve().parents[1] / 'tools/acceptance_lab.py')
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class AcceptanceLabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        home = patch('pathlib.Path.home', return_value=self.base / 'home')
        home.start()
        self.addCleanup(home.stop)

    def test_preflight_does_not_launch_or_authenticate_providers(self):
        with patch.object(lab.shutil, 'which', return_value=None), patch.object(lab.subprocess, 'run') as run:
            result = lab.preflight()
        run.assert_not_called()
        self.assertIsNone(result['authenticated'])
        self.assertFalse(result['provider_sessions_tested'])
        self.assertEqual(result['acceptance_status'], 'pending')

    def test_prepare_all_six_projects_with_clean_work_branches_and_pending_report(self):
        root = self.base / 'lab'
        result = lab.prepare_lab(root, sys.executable)
        self.assertEqual(result['projects'], 6)
        report = json.loads((root / 'acceptance-report.json').read_text())
        self.assertTrue(all(case['status'] == 'pending' for case in report['cases']))
        self.assertTrue(all(case['model'] is None for case in report['cases']))
        for environment in lab.ENVIRONMENTS:
            for scenario in ('fix', 'feature'):
                project = root / environment / scenario
                self.assertTrue(ProjectIntegration(project).check()['ready'])
                self.assertEqual(lab.git(project, 'status', '--porcelain'), '')
                self.assertEqual(lab.git(project, 'branch', '--show-current'), 'test/h05-' + scenario)
                self.assertEqual(lab.git(project, 'config', 'commit.gpgsign'), 'false')
                self.assertEqual(lab.git(project, 'remote'), '')

    def test_existing_destination_and_nested_project_are_not_overwritten(self):
        root = self.base / 'existing'
        root.mkdir()
        (root / 'keep.txt').write_text('Preserve')
        with self.assertRaises(FileExistsError):
            lab.prepare_lab(root, sys.executable)
        self.assertEqual((root / 'keep.txt').read_text(), 'Preserve')
        (root / '.git').mkdir()
        with self.assertRaises(ValueError):
            lab.prepare_lab(root / 'nested', sys.executable)
        self.assertFalse((root / 'nested').exists())

    def test_baselines_expose_the_bug_and_require_the_feature(self):
        for scenario in ('fix', 'feature'):
            project = self.base / scenario
            lab.prepare_project(project, 'chatgpt-checkout', scenario, sys.executable)
            baseline = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'], cwd=project, capture_output=True)
            self.assertEqual(baseline.returncode, 1 if scenario == 'fix' else 0)
            if scenario == 'feature':
                acceptance = subprocess.run([sys.executable, 'acceptance_feature.py'], cwd=project, capture_output=True)
                self.assertNotEqual(acceptance.returncode, 0)
            report = lab.inspect_project(project)
            self.assertEqual(report['acceptance_status'], 'pending_human_review')
            self.assertFalse(report['automated_checks']['completed_flow'])
            self.assertIsNone(report['provider_authenticated'])

    def test_partial_flow_inspection_remains_pending_and_keeps_real_stage(self):
        project = self.base / 'fix'
        lab.prepare_project(project, 'chatgpt-checkout', 'fix', sys.executable)
        state = NativeWorkflow(project).start('fix-lab', 'Correct even sum', 'codex')
        NativeWorkflow(project).lifecycle(state['flow_id'], 'pause')
        report = lab.inspect_project(project)
        self.assertEqual(report['active_flows'][0]['stage'], 'explore')
        self.assertEqual(report['active_flows'][0]['state'], 'paused')
        self.assertTrue(report['automated_checks']['configured_agent_frozen'])
        self.assertFalse(report['automated_checks']['configuration_markers_recorded'])
        self.assertEqual(report['mechanical_result'], 'incomplete')
        self.assertIsNone(report['model'])

    def test_completed_mechanical_case_never_certifies_authentication_or_human_acceptance(self):
        project = self.base / 'completed-fix'
        lab.prepare_project(project, 'codex-cli', 'fix', sys.executable)
        native = NativeWorkflow(project)
        state = native.start('fix-lab', 'Correct even sum in deterministic fixture', 'codex')
        Path(state['evidence_file']).write_text('Reproduced odd/even predicate bug')
        state = native.next(state['flow_id'])
        Path(state['evidence_file']).write_text(lab.AGENT_MARKER + '\n' + lab.SKILL_MARKER)
        source = project / 'app.py'
        source.write_text(source.read_text().replace('!= 0', '== 0'))
        state = native.next(state['flow_id'])
        state = native.next(state['flow_id'])
        Path(state['evidence_file']).write_text(json.dumps({'result': 'approved', 'acceptance_criteria_met': True,
            'mandatory_rules_violated': [], 'findings': [], 'risks': [], 'recommendation': 'Deterministic test fixture only'}))
        state = native.next(state['flow_id'])
        self.assertEqual(state['stage'], 'ready_for_commit')
        lab.git(project, 'add', 'app.py')
        lab.git(project, 'commit', '-m', 'test: close synthetic acceptance-inspector case')
        native.lifecycle(state['flow_id'], 'finish')
        report = lab.inspect_project(project)
        self.assertTrue(all(report['automated_checks'].values()))
        self.assertEqual(report['mechanical_result'], 'ready_for_human_review')
        self.assertEqual(report['acceptance_status'], 'pending_human_review')
        self.assertIsNone(report['provider_authenticated'])
        self.assertIsNone(report['tool_version'])
        self.assertIsNone(report['model'])

    def test_feature_plan_cannot_be_approved_by_lab_inspection(self):
        project = self.base / 'feature'
        lab.prepare_project(project, 'chatgpt-checkout', 'feature', sys.executable)
        native = NativeWorkflow(project)
        state = native.start('feature-lab', 'Add count_even', 'codex')
        Path(state['evidence_file']).write_text('Only sum_even exists; count_even is required.')
        state = native.next(state['flow_id'])
        Path(state['evidence_file']).write_text('Add count_even and tests. Preserve sum_even and baseline tests.')
        state = native.next(state['flow_id'])
        self.assertEqual(state['stage'], 'approve_plan')
        before = (project / 'app.py').read_bytes()
        with self.assertRaises(PermissionError):
            native.next(state['flow_id'])
        report = lab.inspect_project(project)
        self.assertEqual(report['active_flows'][0]['stage'], 'approve_plan')
        self.assertEqual((project / 'app.py').read_bytes(), before)
        self.assertEqual(report['acceptance_status'], 'pending_human_review')

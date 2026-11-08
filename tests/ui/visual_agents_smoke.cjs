/* DOM/API simulation. No real browser, model or project writes. Requires dev-only jsdom. */
const {JSDOM} = require('jsdom');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const templates = JSON.parse(execFileSync(process.env.FACTORIA_TEST_PYTHON || 'python', ['-c',
  'import json; from factoria.application.visual_agents import visual_agent_templates; print(json.dumps([a.to_mapping() for a in visual_agent_templates()]))'],
  {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8'}));
const dom = new JSDOM('<main class="main"><nav class="nav"><button data-page="agents">Plataformas</button><button data-page="designer">Flujos</button></nav><div id="title"></div><section id="agents"><div class="card"><div class="label"></div><div id="agentList"></div></div></section><section id="designer"><div class="workflow-note"></div><select id="workflowKind"><option value="feature">feature</option></select><div id="workflowBoard"></div></section></main>', {runScripts: 'dangerously', url: 'http://localhost/'});
const w = dom.window, d = w.document;
w.structuredClone = structuredClone;
w.state = {selected_project: {path: 'fixture'}, agent_catalog_revision: 'r1',
  agent_roles: [], agent_templates: templates, skills: [], workflows: {}};
w.esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
w.confirm = () => false;
w.renderAll = w.renderWorkflowBoard = w.drawConnections = w.markDirty = () => {};
w.selectProject = w.createProject = w.saveProjectsRoot = w.refresh = async () => {};
w.workflowDraft = []; w.workflowDirty = false; w.workflowOriginId = null;
w.iconFor = () => ''; w.requiredStep = () => true;
w.toast = () => {};
let writes = [];
w.api = async (url, method, body) => {
  writes.push({url, body});
  return {state: {...w.state, agent_catalog_revision: 'r2', agent_roles: [...w.state.agent_roles, body]}};
};
w.eval(fs.readFileSync(path.join(root, 'src/factoria/web/agents.js'), 'utf8'));
(async () => {
  assert.equal(d.querySelectorAll('#agentTemplatePicker option').length, 3);
  w.newVisualAgentRole();
  assert.match(d.getElementById('agentEditorStatus').textContent, /Selecciona/);
  d.getElementById('agentTemplatePicker').value = 'visual-designer';
  d.getElementById('newVisualAgentButton').click();
  assert.equal(d.getElementById('agent-base').value, 'planner');
  assert.equal(d.getElementById('agent-instructions').value, templates[0].instructions);
  assert.equal(writes.length, 0, 'Creating a draft must not write');
  d.getElementById('agent-instructions').value += '\nCustom direction';
  w.newAgentRole('visual-reviewer'); // Discard refused.
  assert.equal(d.getElementById('agent-id').value, 'visual-designer');
  await w.saveAgentRole();
  assert.equal(writes.length, 1);
  assert.equal(writes[0].url, '/api/agent-role/create');
  assert.match(writes[0].body.instructions, /Custom direction/);
  assert.equal(templates[0].instructions.endsWith('Custom direction'), false);
  w.newAgentRole('visual-designer');
  assert.match(d.getElementById('agentEditorStatus').textContent, /Ya existe/);
  assert.equal(writes.length, 1);
  w.workflowDraft = ['planner', 'implementer', 'reviewer'].map((role, i) => ({role, name: role, x: i*270, y: 0, enabled: true}));
  w.renderWorkflowBoard();
  const selectors = d.querySelectorAll('.stage-agent');
  assert.ok([...selectors[0].options].some(o => o.value === 'visual-designer'));
  assert.ok(![...selectors[1].options].some(o => o.value === 'visual-designer'));
  w.newAgentRole('visual-reviewer');
  assert.equal(d.getElementById('agent-base').value, 'reviewer');
  await w.saveAgentRole();
  assert.equal(writes.length, 2);
  assert.equal(writes[1].body.role, 'visual-reviewer');
  dom.window.close();
  console.log('PASS visual templates: draft, cancel, save, duplicate protection and stage compatibility.');
})().catch(e => {dom.window.close(); console.error(e); process.exitCode = 1;});

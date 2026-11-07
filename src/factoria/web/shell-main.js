let workflowDraft = [],
  workflowDirty = false,
  workflowLoadedKind = null,
  drag = null;
function markDirty() {
  workflowDirty = true;
  document.getElementById('workflowDirty').textContent = '• cambios sin guardar';
}
function clearDirty() {
  workflowDirty = false;
  document.getElementById('workflowDirty').textContent = '';
}
let workflowRevision = null,
  workflowProject = null,
  workflowSaving = false,
  workflowCreating = false,
  workflowDraftKind = null,
  workflowOriginId = null;
function workflowBaseKind(id) {
  return workflowLoadedKind === id && workflowDraftKind
    ? workflowDraftKind
    : state.workflows?.[id]?.kind || id;
}
function canLeaveWorkflow() {
  return (
    !workflowSaving &&
    (!workflowDirty || confirm('Hay cambios de flujo sin guardar. ¿Descartarlos?'))
  );
}
window.addEventListener('beforeunload', (event) => {
  if (workflowDirty || workflowSaving) {
    event.preventDefault();
    event.returnValue = '';
  }
});
let refreshPending = false;
async function refresh() {
  if (refreshPending) return;
  refreshPending = true;
  try {
    state = await api('/api/state');
    renderAll();
  } catch (e) {
    toast(e.message);
  } finally {
    refreshPending = false;
  }
}
function renderAll() {
  if (!workflowDirty && workflowProject && workflowProject !== state.selected_project?.path) {
    workflowCreating = false;
    workflowDraftKind = null;
    workflowLoadedKind = null;
    workflowProject = null;
    workflowRevision = null;
    workflowDraft = [];
    clearDirty();
  }
  window.renderWorkflowList?.();
  const p = state.selected_project;
  document.getElementById('subtitle').textContent = p
    ? `${p.name} · ${p.path}`
    : 'Selecciona un proyecto';
  document.getElementById('projectsRootLabel').textContent =
    state.projects_root || 'Sin configurar';
  if (state.projects_root) document.getElementById('projectsRootInput').value = state.projects_root;
  const g = document.getElementById('dashboardGrid');
  window.renderProjectOverview(g, p);
  renderProjects();
  renderAgents();
  renderFlows();
  renderHistory();
  renderSecurity();
  if (document.getElementById('designer').classList.contains('active') && !workflowDirty)
    loadWorkflowBoard(false);
}
function renderProjects() {
  const q = (document.getElementById('projectSearch').value || '').toLowerCase();
  const items = (state.projects || []).filter((p) =>
    (p.name + ' ' + p.path).toLowerCase().includes(q),
  );
  document.getElementById('projectList').innerHTML =
    items
      .map(
        (p) =>
          `<div class="item"><strong>${esc(p.name)}</strong><div class="muted">${esc(p.path)}</div><button class="secondary" onclick='selectProject(${JSON.stringify(p.path)})'>Abrir</button></div>`,
      )
      .join('') || '<div class="muted">No hay proyectos.</div>';
}
function renderAgents() {
  document.getElementById('agentList').innerHTML = (state.agents || [])
    .map(
      (a) =>
        `<div class="item"><strong>${esc(a.name)}</strong><span class="pill ${a.ready ? 'ok' : a.available ? 'warn' : 'bad'}">${a.available ? 'DETECTADO · INICIO EXTERNO' : 'NO DETECTADO'}</span>${state.default_tool === a.name ? '<span class="pill ok">PREDETERMINADO</span>' : ''}<div class="actions"><button class="secondary"  onclick="setDefaultAgent('${esc(a.name)}')">Usar por defecto</button><button class="secondary" onclick="setAgentPath('${esc(a.name)}')">Indicar ruta</button></div></div>`,
    )
    .join('');
}
function renderFlows() {
  const jobs = state.jobs || [];
  document.getElementById('jobList').innerHTML =
    jobs
      .map(
        (j) =>
          `<div class="item"><strong>${esc(j.command)} · ${esc((j.args || []).slice(1).join(' '))}</strong><span class="pill ${j.status === 'completed' ? 'ok' : j.status === 'failed' ? 'bad' : 'warn'}">${esc(j.status)}</span>${j.output ? `<pre>${esc(j.output)}</pre>` : ''}</div>`,
      )
      .join('') || '<div class="muted">Sin ejecuciones recientes.</div>';
  const flows = state.selected_project?.active_flows || [];
  document.getElementById('flowList').innerHTML =
    flows
      .map(
        (f) =>
          `<div class="item"><strong>${esc(f.kind)} · ${esc(f.flow_id)}</strong><div class="muted">${esc(f.state)} ${esc(f.runtime_stage || '')}</div></div>`,
      )
      .join('') || '<div class="muted">No hay flujos persistidos.</div>';
}
function renderHistory() {
  const h = state.selected_project?.history || [];
  document.getElementById('historyList').innerHTML =
    h
      .map(
        (x) =>
          `<div class="item"><strong>${esc(x.kind || x.flow_kind || 'flujo')}</strong><div class="muted">${esc(x.result || x.outcome || x.status || '')}</div></div>`,
      )
      .join('') || '<div class="muted">Sin historial.</div>';
}
function renderSecurity() {
  const s = state.selected_project?.security;
  document.getElementById('securityBody').innerHTML = s
    ? `<div class="value">${s.finding_count || 0} hallazgo(s)</div>`
    : '<div class="muted">Selecciona un proyecto.</div>';
}
async function saveProjectsRoot() {
  if (!canLeaveWorkflow()) return;
  const path = document.getElementById('projectsRootInput').value.trim();
  if (!path) return;
  state = (await api('/api/projects/root', 'POST', { path })).state;
  clearDirty();
  workflowCreating = false;
  renderAll();
  return true;
}
async function selectProject(path) {
  if (!canLeaveWorkflow()) return;
  state = (await api('/api/project/select', 'POST', { path })).state;
  clearDirty();
  workflowCreating = false;
  renderAll();
  return true;
}
async function createProject() {
  if (!canLeaveWorkflow()) return;
  const name = document.getElementById('newName').value.trim();
  if (!name) return toast('Escribe un nombre');
  state = (
    await api('/api/project/create', 'POST', {
      name,
      purpose: document.getElementById('newPurpose').value,
    })
  ).state;
  clearDirty();
  workflowCreating = false;
  renderAll();
  return true;
}
async function setDefaultAgent(tool) {
  state = (await api('/api/agent/default', 'POST', { tool })).state;
  renderAll();
}
async function setAgentPath(tool) {
  const path = prompt(`Ruta completa de ${tool}:`, '');
  if (!path) return;
  state = (await api('/api/agent/path', 'POST', { tool, path })).state;
  renderAll();
}
function canonicalX(i) {
  return 90 + i * 270;
}
function nodeY(i) {
  return 64 + (i % 2) * 12;
}
function iconFor(n) {
  return { explore: '01', plan: '02', implement: '03', review: '04', document: '05' }[n] || '·';
}
function requiredStep(kind, name) {
  return workflowBaseKind(kind) === 'feature' || ['explore', 'implement', 'review'].includes(name);
}
function loadWorkflowBoard(force = false) {
  if (workflowDirty && !force) return;
  const project = state.selected_project?.path || null;
  const kind = document.getElementById('workflowKind').value;
  const source = state.workflows?.[kind];
  if (
    !force &&
    workflowLoadedKind === kind &&
    workflowProject === project &&
    workflowDraft.length &&
    workflowRevision === source?.revision
  )
    return;
  if (!project || !source || source.error) {
    document.getElementById('workflowBoard').textContent =
      source?.error || 'Selecciona un proyecto.';
    workflowRevision = null;
    return;
  }
  workflowDraft = (source.steps || []).map((s, i) => ({ ...s, x: canonicalX(i), y: nodeY(i) }));
  workflowRevision = source.revision;
  workflowProject = project;
  workflowLoadedKind = kind;
  workflowDraftKind = source.kind;
  window.loadWorkflowMetadata?.(source);
  clearDirty();
  renderWorkflowBoard();
}
function renderWorkflowBoard() {
  const kind = document.getElementById('workflowKind').value;
  document.getElementById('workflowBoard').innerHTML = workflowDraft
    .map(
      (s, i) =>
        `<div class="node ${s.enabled ? '' : 'off'}" data-i="${i}" style="left:${s.x}px;top:${s.y}px" onpointerdown="startNodeDrag(event,${i})"><span class="port in"></span><span class="port out"></span><div class="node-header"><div class="node-icon">${iconFor(s.name)}</div><div><div class="node-title">${esc(s.name)}</div><div class="muted" style="font-size:12px">${esc(s.role)}</div></div></div><div class="node-body"><select onclick="event.stopPropagation()" onchange="setNodeTool(${i},this.value)"><option value="" ${!s.tool ? 'selected' : ''}>Agente predeterminado</option><option value="codex" ${s.tool === 'codex' ? 'selected' : ''}>Codex</option><option value="opencode" ${s.tool === 'opencode' ? 'selected' : ''}>OpenCode</option></select>${requiredStep(kind, s.name) ? '<div class="node-lock">Etapa obligatoria</div>' : `<label class="node-toggle" onclick="event.stopPropagation()"><input type="checkbox" ${s.enabled ? 'checked' : ''} onchange="toggleNode(${i},this.checked)"> etapa activa</label>`}<div class="node-meta"><span class="pill">${s.enabled ? 'activa' : 'apagada'}</span></div></div></div>`,
    )
    .join('');
  drawConnections();
}
function drawConnections() {
  const enabled = workflowDraft.filter((x) => x.enabled).sort((a, b) => a.x - b.x);
  const svg = document.getElementById('connections');
  svg.innerHTML = '';
  for (let i = 0; i < enabled.length - 1; i++) {
    const a = enabled[i],
      b = enabled[i + 1],
      source = document.querySelector(`#workflowBoard .node[data-i="${workflowDraft.indexOf(a)}"]`),
      target = document.querySelector(`#workflowBoard .node[data-i="${workflowDraft.indexOf(b)}"]`),
      x1 = a.x + (source?.offsetWidth || 220),
      y1 = a.y + (source?.offsetHeight || 190) / 2,
      x2 = b.x,
      y2 = b.y + (target?.offsetHeight || 190) / 2,
      m = (x1 + x2) / 2;
    svg.insertAdjacentHTML(
      'beforeend',
      `<path d="M ${x1} ${y1} C ${m} ${y1}, ${m} ${y2}, ${x2} ${y2}"/>`,
    );
  }
}
function startNodeDrag(e, i) {
  if (e.target.closest('select,input,label,button')) return;
  drag = { i, startX: e.clientX, origX: workflowDraft[i].x };
  e.currentTarget.setPointerCapture(e.pointerId);
  e.currentTarget.classList.add('dragging');
  e.currentTarget.onpointermove = moveNode;
  e.currentTarget.onpointerup = endNodeDrag;
}
function moveNode(e) {
  if (!drag) return;
  workflowDraft[drag.i].x = Math.max(35, drag.origX + (e.clientX - drag.startX));
  e.currentTarget.style.left = workflowDraft[drag.i].x + 'px';
  drawConnections();
  markDirty();
}
function endNodeDrag(e) {
  if (!drag) return;
  e.currentTarget.classList.remove('dragging');
  workflowDraft.sort((a, b) => a.x - b.x);
  workflowDraft.forEach((s, i) => {
    s.x = canonicalX(i);
    s.y = nodeY(i);
  });
  drag = null;
  renderWorkflowBoard();
}
function setNodeTool(i, v) {
  workflowDraft[i].tool = v || null;
  markDirty();
}
function toggleNode(i, v) {
  workflowDraft[i].enabled = v;
  markDirty();
  renderWorkflowBoard();
}
function fitCanvas() {
  document.getElementById('workflowCanvas').scrollTo({ left: 0, top: 0, behavior: 'smooth' });
}
async function changeWorkflowKind() {
  const target = document.getElementById('workflowKind').value;
  if (!canLeaveWorkflow()) {
    document.getElementById('workflowKind').value = workflowLoadedKind || 'feature';
    return;
  }
  try {
    state = await api('/api/state');
    clearDirty();
    workflowCreating = false;
    workflowLoadedKind = null;
    window.renderWorkflowList?.(target);
    loadWorkflowBoard(true);
  } catch (e) {
    document.getElementById('workflowKind').value = workflowLoadedKind || 'feature';
    toast(e.message);
  }
}
async function saveWorkflow() {
  if (workflowSaving) return;
  if (!workflowProject || workflowProject !== state.selected_project?.path || !workflowRevision)
    return toast('Vuelve a cargar el flujo del proyecto antes de guardar');
  const kind = workflowDraftKind || workflowLoadedKind;
  const id = workflowCreating
    ? document.getElementById('workflowId').value.trim()
    : state.workflows?.[workflowLoadedKind]?.id || null;
  const payload = {
    kind,
    id,
    name: id ? document.getElementById('workflowName').value.trim() : '',
    description: id ? document.getElementById('workflowDescription').value : '',
    steps: [...workflowDraft].sort((a, b) => a.x - b.x).map(({ x, y, ...s }) => s),
    project_path: workflowProject,
    revision: workflowRevision,
  };
  workflowSaving = true;
  document.getElementById('designer').inert = true;
  try {
    const d = await api(
      workflowCreating ? '/api/workflow/create' : '/api/workflow/save',
      'POST',
      payload,
    );
    state = d.state;
    clearDirty();
    workflowCreating = false;
    workflowLoadedKind = null;
    window.renderWorkflowList?.(id || kind);
    loadWorkflowBoard(true);
    toast('Flujo guardado; prepara la integración');
  } catch (e) {
    workflowDirty = true;
    document.getElementById('workflowDirty').textContent =
      '• ' + e.message + ' · Borrador conservado';
    toast(e.message);
  } finally {
    workflowSaving = false;
    document.getElementById('designer').inert = false;
  }
}
async function resetWorkflowLocal() {
  if (!canLeaveWorkflow()) return;
  const target = workflowCreating ? workflowOriginId || 'feature' : workflowLoadedKind;
  try {
    state = await api('/api/state');
    clearDirty();
    workflowCreating = false;
    workflowLoadedKind = null;
    window.renderWorkflowList?.(target);
    loadWorkflowBoard(true);
    toast('Flujo recargado; cambios descartados');
  } catch (e) {
    toast(e.message);
  }
}
async function runCommand(args) {
  try {
    const d = await api('/api/command', 'POST', { args });
    document.getElementById('commandOutput').textContent = d.output || '(sin salida)';
    state = d.state;
    renderAll();
    return d;
  } catch (e) {
    toast(e.message);
  }
}
async function initMemory() {
  const p = state.selected_project;
  if (p) await runCommand(['memoria-init', '--name', p.name, '--yes']);
}
async function runFlow(kind) {
  toast('Abre Codex/OpenCode fuera de Factoría y solicita allí el flujo ' + kind);
}
async function pollJob(id) {
  try {
    const d = await api('/api/job/' + id);
    state = d.state;
    renderAll();
    if (['queued', 'running'].includes(d.job.status)) setTimeout(() => pollJob(id), 1500);
  } catch (e) {
    toast(e.message);
  }
}
function tokenize(s) {
  return s.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g)?.map((x) => x.replace(/^["']|["']$/g, '')) || [];
}
function executeTypedCommand() {
  const args = tokenize(
    document
      .getElementById('commandInput')
      .value.trim()
      .replace(/^factoria\s+/, ''),
  );
  if (args.length) runCommand(args);
}
document.querySelectorAll('.nav button').forEach(
  (b) =>
    (b.onclick = () => {
      document.querySelectorAll('.nav button').forEach((x) => x.classList.remove('active'));
      document.querySelectorAll('.section').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      document.getElementById(b.dataset.page).classList.add('active');
      document.getElementById('title').textContent = b.textContent;
      if (b.dataset.page === 'designer') loadWorkflowBoard(false);
    }),
);
refresh();
setInterval(() => {
  if (!workflowDirty) refresh();
}, 5000);

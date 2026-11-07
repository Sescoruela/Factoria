let workflowDraft = [];
let draggedIndex = null;
let workflowDirty = false;
let workflowLoadedKind = null;

function markWorkflowDirty() {
  workflowDirty = true;
  document.getElementById('workflowDirty').textContent = '• cambios sin guardar';
}
function clearWorkflowDirty() {
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
    clearWorkflowDirty();
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
  const q = (document.getElementById('projectSearch')?.value || '').toLowerCase();
  const el = document.getElementById('projectList');
  const items = (state.projects || []).filter((p) =>
    (p.name + ' ' + p.path).toLowerCase().includes(q),
  );
  el.innerHTML =
    items
      .map(
        (p) =>
          `<div class="item"><strong>${esc(p.name)}</strong><div class="muted">${esc(p.path)}</div><button class="secondary" onclick='selectProject(${JSON.stringify(p.path)})'>Abrir</button></div>`,
      )
      .join('') || '<div class="muted">No hay proyectos.</div>';
}
function renderAgents() {
  const el = document.getElementById('agentList');
  el.innerHTML = (state.agents || [])
    .map((a) => {
      const desktop =
        a.name === 'codex' && a.desktop_detected && !a.available
          ? '<span class="pill warn">CHATGPT DESKTOP DETECTADO</span>'
          : '';
      const source = a.cli_source ? `<div class="muted">CLI: ${esc(a.cli_source)}</div>` : '';
      const details = (a.checks || [])
        .filter((c) => !c.passed && c.details)
        .map((c) => `<div class="muted">${esc(c.details)}</div>`)
        .join('');
      return `<div class="item"><strong>${esc(a.name)}</strong><span class="pill ${a.ready ? 'ok' : a.available ? 'warn' : 'bad'}">${a.available ? 'DETECTADO · INICIO EXTERNO' : 'NO DETECTADO'}</span>${desktop}${state.default_tool === a.name ? '<span class="pill ok">PREDETERMINADO</span>' : ''}${source}${details}<div class="actions"><button class="secondary"  onclick="setDefaultAgent('${esc(a.name)}')">Usar por defecto</button><button class="secondary" onclick="setAgentPath('${esc(a.name)}')">Indicar ruta CLI</button></div></div>`;
    })
    .join('');
}
function renderFlows() {
  const jobs = state.jobs || [];
  document.getElementById('jobList').innerHTML =
    jobs
      .map(
        (j) =>
          `<div class="item"><strong>${esc(j.command)} · ${esc((j.args || []).slice(1).join(' '))}</strong><span class="pill ${j.status === 'completed' ? 'ok' : j.status === 'failed' ? 'bad' : 'warn'}">${esc(j.status)}</span>${j.status === 'running' ? '<div class="muted">El agente está trabajando. La web sigue disponible.</div>' : ''}${j.output ? `<pre>${esc(j.output)}</pre>` : ''}</div>`,
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
async function changeWorkflowKind() {
  const target = document.getElementById('workflowKind').value;
  if (!canLeaveWorkflow()) {
    document.getElementById('workflowKind').value = workflowLoadedKind || 'feature';
    return;
  }
  try {
    state = await api('/api/state');
    clearWorkflowDirty();
    workflowCreating = false;
    workflowLoadedKind = null;
    window.renderWorkflowList?.(target);
    loadWorkflowBoard(true);
  } catch (e) {
    document.getElementById('workflowKind').value = workflowLoadedKind || 'feature';
    toast(e.message);
  }
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
  workflowDraft = (source.steps || []).map((s, i) => ({ ...s }));
  workflowRevision = source.revision;
  workflowProject = project;
  workflowLoadedKind = kind;
  workflowDraftKind = source.kind;
  window.loadWorkflowMetadata?.(source);
  clearWorkflowDirty();
  renderWorkflowBoard();
}
function isOptionalStep(kind, name) {
  return workflowBaseKind(kind) === 'fix' && (name === 'plan' || name === 'document');
}
function titleForStep(name) {
  return (
    {
      explore: 'Explorer',
      plan: 'Planner',
      implement: 'Implementer',
      review: 'Reviewer',
      document: 'Documenter',
    }[name] || name
  );
}
function descriptionForStep(name) {
  return (
    {
      explore: 'Entiende código, contexto e impacto.',
      plan: 'Diseña el plan y criterios de aceptación.',
      implement: 'Realiza los cambios aprobados.',
      review: 'Revisa diff, reglas, riesgos y verificación.',
      document: 'Propone actualización de memoria/documentación.',
    }[name] || ''
  );
}
function renderWorkflowBoard() {
  const kind = document.getElementById('workflowKind').value;
  const el = document.getElementById('workflowBoard');
  if (!state.selected_project) {
    el.innerHTML = '<div class="muted">Selecciona un proyecto para personalizar su flujo.</div>';
    return;
  }
  el.innerHTML = workflowDraft
    .map(
      (s, i) =>
        `<div class="flow-card ${s.enabled === false ? 'muted' : ''}" draggable="true" data-index="${i}" ondragstart="dragStart(event,${i})" ondragover="dragOver(event)" ondragleave="dragLeave(event)" ondrop="dropCard(event,${i})" ondragend="dragEnd(event)"><div class="drag-handle">⋮⋮</div><div><strong>${i + 1}. ${esc(titleForStep(s.name))}</strong><div class="muted">${esc(descriptionForStep(s.name))}</div><div class="flow-meta"><span class="pill">${esc(s.role)}</span>${isOptionalStep(kind, s.name) ? '<span class="pill warn">OPCIONAL</span>' : '<span class="pill ok">OBLIGATORIO</span>'}</div></div><div class="flow-controls"><label>Agente de la etapa<select class="stage-agent" onchange="setStepAgent(${i},this.value)"><option value="" ${!s.agent_id ? 'selected' : ''}>Predeterminado (${esc(s.role)})</option>${(
          state.workflows?.[kind]?.agents ||
          state.workflows?.[workflowOriginId]?.agents ||
          []
        )
          .filter((a) => (a.base_role || a.role) === s.role)
          .map(
            (a) =>
              `<option value="${a.role}" ${s.agent_id === a.role ? 'selected' : ''}>${esc(a.name || a.role)}</option>`,
          )
          .join(
            '',
          )}${s.agent_id && !(state.workflows?.[kind]?.agents || state.workflows?.[workflowOriginId]?.agents || []).some((a) => a.role === s.agent_id && (a.base_role || a.role) === s.role) ? `<option selected value="${esc(s.agent_id)}">${esc(s.agent_id)} · no disponible</option>` : ''}</select></label><select onchange="setStepTool(${i},this.value)"><option value="" ${!s.tool ? 'selected' : ''}>Agente predeterminado</option><option value="codex" ${s.tool === 'codex' ? 'selected' : ''}>Codex</option><option value="opencode" ${s.tool === 'opencode' ? 'selected' : ''}>OpenCode</option></select>${isOptionalStep(kind, s.name) ? `<label class="toggle"><input type="checkbox" ${s.enabled !== false ? 'checked' : ''} onchange="setStepEnabled(${i},this.checked)"> Etapa activa</label>` : '<div class="lock">Etapa obligatoria</div>'}</div></div>${i < workflowDraft.length - 1 ? '<div class="flow-arrow">↓</div>' : ''}`,
    )
    .join('');
}
function dragStart(e, i) {
  draggedIndex = i;
  e.currentTarget.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
}
function dragOver(e) {
  e.preventDefault();
  e.currentTarget.classList.add('drag-over');
}
function dragLeave(e) {
  e.currentTarget.classList.remove('drag-over');
}
function dropCard(e, i) {
  e.preventDefault();
  if (draggedIndex === null || draggedIndex === i) return;
  const [moved] = workflowDraft.splice(draggedIndex, 1);
  workflowDraft.splice(i, 0, moved);
  draggedIndex = null;
  markWorkflowDirty();
  renderWorkflowBoard();
}
function dragEnd(e) {
  e.currentTarget.classList.remove('dragging');
  document.querySelectorAll('.flow-card').forEach((x) => x.classList.remove('drag-over'));
  draggedIndex = null;
}
function setStepAgent(i, v) {
  workflowDraft[i].agent_id = v || null;
  markWorkflowDirty();
}
function setStepTool(i, v) {
  workflowDraft[i].tool = v || null;
  markWorkflowDirty();
}
function setStepEnabled(i, v) {
  workflowDraft[i].enabled = v;
  markWorkflowDirty();
  renderWorkflowBoard();
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
    steps: structuredClone(workflowDraft),
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
    clearWorkflowDirty();
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
    clearWorkflowDirty();
    workflowCreating = false;
    workflowLoadedKind = null;
    window.renderWorkflowList?.(target);
    loadWorkflowBoard(true);
    toast('Flujo recargado; cambios descartados');
  } catch (e) {
    toast(e.message);
  }
}
async function saveProjectsRoot() {
  if (!canLeaveWorkflow()) return;
  const path = document.getElementById('projectsRootInput').value.trim();
  if (!path) return;
  state = (await api('/api/projects/root', 'POST', { path })).state;
  clearWorkflowDirty();
  workflowCreating = false;
  renderAll();
  return true;
}
async function selectProject(path) {
  if (!canLeaveWorkflow()) return;
  state = (await api('/api/project/select', 'POST', { path })).state;
  clearWorkflowDirty();
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
  clearWorkflowDirty();
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
    if (['queued', 'running'].includes(d.job.status)) {
      setTimeout(() => pollJob(id), 1500);
    } else {
      toast(d.job.status === 'completed' ? 'Flujo terminado' : 'Flujo terminado con error');
    }
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
      if (b.dataset.page === 'designer' && !workflowDirty) loadWorkflowBoard(true);
    }),
);
refresh();
setInterval(refresh, 5000);

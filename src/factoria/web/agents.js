(function () {
  let agentEdits = false;
  let agentProject = null;
  let agentDraft = null;
  let agentRevision = null;
  let agentCreating = false;
  let agentSaving = false;
  window.hasUnsavedAgents = () => agentEdits || agentSaving;
  const roleLabels = {
    explorer: 'Explorer',
    planner: 'Planner',
    implementer: 'Implementer',
    reviewer: 'Reviewer',
    documenter: 'Documenter',
  };
  const roleNotes = {
    explorer: 'Explora el repositorio sin modificarlo.',
    planner: 'Define plan, criterios y riesgos.',
    implementer: 'Realiza cambios autorizados en el proyecto.',
    reviewer: 'Revisa cambios y devuelve una evaluación estructurada.',
    documenter: 'Propone actualizaciones de memoria y documentación.',
  };
  const nav = document.querySelector('.nav');
  const platformButton = document.querySelector('.nav button[data-page="agents"]');
  if (platformButton) platformButton.textContent = 'Plataformas';
  if (nav && !document.querySelector('.nav button[data-page="agentRoles"]')) {
    const b = document.createElement('button');
    b.dataset.page = 'agentRoles';
    b.textContent = 'Agentes';
    const designer = document.querySelector('.nav button[data-page="designer"]');
    nav.insertBefore(b, designer || null);
    b.onclick = () => openAgentRoles(b);
  }
  if (!document.getElementById('agentRoles')) {
    const s = document.createElement('section');
    s.id = 'agentRoles';
    s.className = 'section';
    s.innerHTML =
      '<div class="concept-note"><strong>Agentes de Factoria</strong><div class="muted">Define las instrucciones y skills de cada especialista. Después podrás asignarlo a una etapa y preparar el proyecto para Codex u OpenCode.</div></div><div class="actions"><button class="primary" id="newAgentButton" onclick="newAgentRole()">Crear agente</button><label>Plantilla de agente<select id="agentTemplatePicker"><option value="">Selecciona una plantilla…</option></select></label><button class="secondary" id="newVisualAgentButton" onclick="newVisualAgentRole()">Crear desde plantilla</button></div><p id="agentEditorStatus" role="status" aria-live="polite"></p><div id="agentRoleList" class="agent-grid"></div><div id="agentRoleEditor"></div>';
    document.querySelector('main.main').appendChild(s);
  }
  function openAgentRoles(button) {
    document.querySelectorAll('.nav button').forEach((x) => x.classList.remove('active'));
    document.querySelectorAll('.section').forEach((x) => x.classList.remove('active'));
    button.classList.add('active');
    document.getElementById('agentRoles').classList.add('active');
    document.getElementById('title').textContent = 'Agentes';
    renderAgentRoles();
  }
  function agentStatus(message) {
    document.getElementById('agentEditorStatus').textContent = message;
  }
  function canLeaveAgent() {
    return (
      !agentSaving && (!agentEdits || confirm('Hay cambios de agente sin guardar. ¿Descartarlos?'))
    );
  }
  window.renderAgentRoles = function () {
    const picker = document.getElementById('agentTemplatePicker');
    if (picker && !agentEdits && !agentSaving) {
      const selected = picker.value;
      picker.innerHTML =
        '<option value="">Selecciona una plantilla…</option>' +
        (state.agent_templates || [])
          .map((a) => `<option value="${esc(a.role)}">${esc(a.name)}</option>`)
          .join('');
      picker.value = selected;
    }
    const project = state.selected_project?.path || null;
    if (project !== agentProject) {
      if (agentEdits || agentSaving) {
        agentStatus(
          'Borrador de otro proyecto conservado. Vuelve al proyecto de origen o descarta / recarga.',
        );
        return;
      }
      agentDraft = null;
      agentProject = project;
      agentRevision = null;
    }
    const el = document.getElementById('agentRoleList');
    if (!el) return;
    for (const id of ['newAgentButton', 'newVisualAgentButton', 'agentTemplatePicker']) {
      document.getElementById(id).disabled =
        !project || agentSaving || !!state.agent_configuration_error;
    }
    if (agentEdits || agentSaving) return;
    if (state.agent_configuration_error) {
      el.textContent = state.agent_configuration_error;
      document.getElementById('agentRoleEditor').innerHTML = '';
      agentStatus('No se puede editar el catálogo hasta corregir su configuración.');
      return;
    }
    if (!project) {
      el.textContent = 'Selecciona un proyecto para editar sus agentes.';
      document.getElementById('agentRoleEditor').innerHTML = '';
      agentStatus('');
      return;
    }
    if (!state.agent_roles) return;
    const items = state.agent_roles;
    el.innerHTML = items
      .map(
        (a) =>
          `<div class="agent-editor" data-resource-id="${esc(a.role)}"><h3>${esc(a.name || roleLabels[a.role] || a.role)}</h3><div class="role-note">${esc(a.role)} · ${esc(roleLabels[a.base_role || a.role] || '')}</div><p>${esc(a.description || roleNotes[a.base_role || a.role] || '')}</p><button class="secondary" onclick="editAgentRole('${a.role}')">Modificar</button></div>`,
      )
      .join('');
    if (!agentDraft)
      document.getElementById('agentRoleEditor').innerHTML =
        '<div class="editor-placeholder"><h3>Selecciona un agente</h3><p>Abre uno de la lista para revisar sus instrucciones y skills, o crea un especialista nuevo.</p></div>';
    if (agentDraft) {
      const current = items.find((a) => a.role === agentDraft.role);
      if (current) {
        agentDraft = structuredClone(current);
        agentRevision = state.agent_catalog_revision;
        renderAgentEditor();
      }
    }
  };
  window.newVisualAgentRole = function () {
    const id = document.getElementById('agentTemplatePicker').value;
    if (!id) return agentStatus('Selecciona una plantilla de agente.');
    window.newAgentRole(id);
  };
  window.newAgentRole = function (templateId) {
    if (
      !state.selected_project ||
      !state.agent_catalog_revision ||
      state.agent_configuration_error ||
      !canLeaveAgent()
    )
      return;
    const template = templateId
      ? (state.agent_templates || []).find((a) => a.role === templateId)
      : null;
    if (templateId && !template) return agentStatus('Selecciona una plantilla válida.');
    if (template && (state.agent_roles || []).some((a) => a.role === template.role))
      return agentStatus(
        'Ya existe ese especialista. Modifícalo o crea uno con otro identificador.',
      );
    agentDraft = template
      ? structuredClone(template)
      : {
          role: '',
          name: '',
          description: '',
          base_role: 'implementer',
          profile: 'equilibrado',
          platform: null,
          instructions: '',
          skills: [],
        };
    agentRevision = state.agent_catalog_revision;
    agentCreating = true;
    agentEdits = true;
    renderAgentEditor();
    agentStatus(
      template
        ? 'Plantilla cargada · revisa y guarda el agente; después asígnalo a su etapa en el diseñador.'
        : 'Nuevo agente · cambios sin guardar',
    );
  };
  window.editAgentRole = function (role) {
    if (!canLeaveAgent() || state.agent_configuration_error) return;
    const item = (state.agent_roles || []).find((a) => a.role === role);
    if (!item) return;
    agentDraft = structuredClone(item);
    agentRevision = state.agent_catalog_revision;
    agentCreating = false;
    agentEdits = false;
    renderAgentEditor();
    agentStatus('Agente guardado');
  };
  function renderAgentEditor() {
    const a = agentDraft;
    document
      .querySelectorAll('#agentRoleList [data-resource-id]')
      .forEach((item) => item.classList.toggle('selected', item.dataset.resourceId === a?.role));
    if (!a) return;
    const base = a.base_role || a.role;
    const fixed = !!roleLabels[a.role] && !agentCreating;
    document.getElementById('agentRoleEditor').innerHTML =
      `<div class="agent-editor" style="margin-top:16px"><fieldset id="agent-fields" style="border:0;padding:0;margin:0"><h3>${agentCreating ? 'Crear agente' : 'Modificar agente'}</h3><label>Identificador<input id="agent-id" maxlength="64" value="${esc(a.role)}" ${agentCreating ? '' : 'disabled'} placeholder="revisor-api"><span class="muted">Minúsculas, números y guiones. Se conserva al modificar.</span></label><label>Nombre<input id="agent-name" maxlength="120" value="${esc(a.name || roleLabels[a.role] || '')}"></label><label>Descripción<textarea id="agent-description" rows="2" maxlength="1000">${esc(a.description || '')}</textarea></label><label>Rol base<select id="agent-base" ${fixed ? 'disabled' : ''}>${Object.entries(
        roleLabels,
      )
        .map(
          ([id, label]) =>
            `<option value="${id}" ${base === id ? 'selected' : ''}>${label}</option>`,
        )
        .join(
          '',
        )}</select></label><label>Perfil de modelo<select id="agent-profile">${['rapido', 'equilibrado', 'potente'].map((v) => `<option value="${v}" ${a.profile === v ? 'selected' : ''}>${v}</option>`).join('')}</select></label><label>Plataforma preferida<select id="agent-platform"><option value="" ${!a.platform ? 'selected' : ''}>Predeterminada</option><option value="codex" ${a.platform === 'codex' ? 'selected' : ''}>Codex</option><option value="opencode" ${a.platform === 'opencode' ? 'selected' : ''}>OpenCode</option></select></label><label>Instrucciones del agente<textarea id="agent-instructions" rows="6" maxlength="20000">${esc(a.instructions || '')}</textarea></label><label>Añadir skill del catálogo<select id="agentSkillPicker" onchange="assignCatalogSkill(this.value);this.value=''"><option value="">Selecciona una skill…</option>${(state.skills || []).map((skill) => `<option value="${esc(skill.path)}">${esc(skill.name)}</option>`).join('')}</select></label><label>Skills existentes · una ruta Markdown relativa por línea<textarea id="agent-skills" rows="3">${esc((a.skills || []).join('\n'))}</textarea></label><div class="actions"><button class="primary" id="saveAgentButton" onclick="saveAgentRole()">Guardar agente</button><button class="secondary" onclick="discardAgentRole()">Descartar / recargar</button></div><p class="muted">Tras guardar, prepara la integración para actualizar las dos herramientas. Los flujos ya iniciados conservan su snapshot.</p></fieldset></div>`;
  }
  window.discardAgentRole = async function () {
    if (!canLeaveAgent()) return;
    try {
      const latest = await api('/api/state');
      state = latest;
      agentEdits = false;
      agentDraft = null;
      agentRevision = null;
      document.getElementById('agentRoleEditor').innerHTML = '';
      renderAll();
      agentStatus('Catálogo recargado; cambios descartados');
    } catch (e) {
      agentStatus(e.message);
    }
  };
  window.saveAgentRole = async function () {
    if (!agentDraft || agentSaving) return;
    if (agentProject !== state.selected_project?.path)
      return agentStatus('Vuelve al proyecto de origen del borrador antes de guardar.');
    const payload = {
      role: document.getElementById('agent-id').value.trim(),
      name: document.getElementById('agent-name').value.trim(),
      description: document.getElementById('agent-description').value,
      base_role: document.getElementById('agent-base').value,
      profile: document.getElementById('agent-profile').value,
      platform: document.getElementById('agent-platform').value || null,
      instructions: document.getElementById('agent-instructions').value,
      skills: document
        .getElementById('agent-skills')
        .value.split('\n')
        .map((s) => s.trim())
        .filter(Boolean),
      project_path: agentProject,
      revision: agentRevision,
    };
    if (!payload.name) return agentStatus('Escribe un nombre para el agente');
    agentSaving = true;
    document.getElementById('agent-fields').disabled = true;
    document.getElementById('saveAgentButton').disabled = true;
    agentStatus('Guardando…');
    try {
      const d = await api(
        agentCreating ? '/api/agent-role/create' : '/api/agent-role/save',
        'POST',
        payload,
      );
      state = d.state;
      agentEdits = false;
      agentCreating = false;
      agentDraft = structuredClone(state.agent_roles.find((a) => a.role === payload.role));
      agentRevision = state.agent_catalog_revision;
      agentStatus('Guardado. Integración pendiente de actualizar.');
    } catch (e) {
      agentEdits = true;
      agentStatus(e.message + ' · Tu borrador se conserva.');
    } finally {
      agentSaving = false;
      document.getElementById('agent-fields').disabled = false;
      document.getElementById('saveAgentButton').disabled = false;
      if (!agentEdits) renderAll();
    }
  };
  function applyTerminology() {
    const label = document.querySelector('#agents .label');
    if (label) label.textContent = 'Plataformas · Codex / OpenCode';
    const platformCard = document.querySelector('#agents .card');
    if (platformCard && !platformCard.querySelector('.platform-explain')) {
      const p = document.createElement('div');
      p.className = 'muted platform-explain';
      p.style.marginBottom = '10px';
      p.textContent =
        'Estas plataformas ejecutan los agentes y seleccionan el LLM según la configuración de Factoria.';
      platformCard.insertBefore(p, document.getElementById('agentList'));
    }
    document.querySelectorAll('#dashboardGrid .card').forEach((c) => {
      const l = c.querySelector('.label');
      if (!l) return;
      if (l.textContent === 'Agente') l.textContent = 'Plataforma';
      if (l.textContent === 'Perfil') l.textContent = 'Perfil de permisos';
    });
    renderAgentRoles();
  }
  document.getElementById('agentRoleEditor').addEventListener('input', () => {
    agentEdits = true;
    agentStatus('Cambios sin guardar');
  });
  window.addEventListener('beforeunload', (event) => {
    if (agentEdits || agentSaving) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  const integrationSection = document.createElement('section');
  integrationSection.id = 'integration';
  integrationSection.className = 'section';
  integrationSection.innerHTML =
    '<div class="card"><h2>Preparar proyecto para Codex y OpenCode</h2><p>Configura agentes y flujos, revisa los archivos que se generarán y guarda el resultado en Git. Después podrás trabajar directamente en cualquiera de las dos herramientas con Factoría cerrada.</p><div id="integrationStatus"></div><div class="actions"><button onclick="prepareIntegration(false)">Ver cambios</button><button class="primary" onclick="prepareIntegration(true)">Preparar ambas herramientas</button></div><pre id="integrationOutput"></pre><p>Codex: usa las skills factoria-fix y factoria-feature. OpenCode: también puedes usar /factoria-fix y /factoria-feature. Las peticiones naturales se dirigen desde AGENTS.md.</p><p>ChatGPT necesita acceso al repositorio. Para una conversación sin ese acceso, adjunta .factoria/generated/chatgpt-context.md y el código necesario; sin herramientas solo podrá proponer cambios.</p><p>Los modelos y permisos se controlan en Codex/OpenCode. Una etapa asignada a otra plataforma requiere continuar allí.</p></div>';
  document.querySelector('main.main').appendChild(integrationSection);
  const integrationButton = document.createElement('button');
  integrationButton.textContent = 'Integración';
  integrationButton.dataset.page = 'integration';
  nav.appendChild(integrationButton);
  integrationButton.onclick = () => {
    document.querySelectorAll('.nav button').forEach((b) => b.classList.remove('active'));
    document.querySelectorAll('.section').forEach((s) => s.classList.remove('active'));
    integrationButton.classList.add('active');
    integrationSection.classList.add('active');
    document.getElementById('title').textContent = 'Integración';
    renderIntegration();
  };
  window.prepareIntegration = async function (apply) {
    try {
      if (agentEdits || workflowDirty || window.hasUnsavedSkills?.())
        return toast('Guarda primero los cambios de skills, agentes y flujos.');
      const preview = await api('/api/project/prepare', 'POST', { confirmed: false });
      document.getElementById('integrationOutput').textContent = JSON.stringify(
        { archivos: preview.changed, conflictos: preview.conflicts },
        null,
        2,
      );
      if (!apply) return;
      if (preview.conflicts.length)
        return toast('Resuelve los conflictos antes de preparar el proyecto.');
      if (
        !confirm(
          'Se actualizarán únicamente los archivos mostrados. Se conserva el contenido propio de AGENTS.md. ¿Aplicar?',
        )
      )
        return;
      const result = await api('/api/project/prepare', 'POST', { confirmed: true });
      state = result.state;
      renderIntegration();
      toast('Proyecto preparado. Revisa y guarda los cambios en Git.');
    } catch (e) {
      toast(e.message);
    }
  };
  function renderIntegration() {
    const i = state.integration;
    document.getElementById('integrationStatus').textContent = !state.selected_project
      ? 'Selecciona un proyecto.'
      : i?.error ||
        (i?.ready
          ? 'Integración preparada y actualizada.'
          : 'Integración pendiente o desactualizada.');
  }
  const previousSelectProject = selectProject;
  selectProject = async function (path) {
    if (!canLeaveAgent()) return;
    if ((await previousSelectProject(path)) !== true) return;
    agentEdits = false;
    agentDraft = null;
    document.getElementById('agentRoleEditor').innerHTML = '';
    await refresh();
  };
  const previousCreateProject = createProject;
  createProject = async function () {
    if (!canLeaveAgent()) return;
    if ((await previousCreateProject()) !== true) return;
    agentEdits = false;
    agentDraft = null;
    document.getElementById('agentRoleEditor').innerHTML = '';
    await refresh();
  };
  const previousSaveProjectsRoot = saveProjectsRoot;
  saveProjectsRoot = async function () {
    if (!canLeaveAgent()) return;
    if ((await previousSaveProjectsRoot()) !== true) return;
    agentEdits = false;
    agentDraft = null;
    document.getElementById('agentRoleEditor').innerHTML = '';
    await refresh();
  };
  const oldRenderAll = renderAll;
  renderAll = function () {
    oldRenderAll();
    applyTerminology();
    renderIntegration();
  };
  const oldRenderWorkflowBoard = renderWorkflowBoard;
  renderWorkflowBoard = function () {
    const kind = document.getElementById('workflowKind').value;
    const candidates =
      state.workflows?.[kind]?.agents ||
      state.workflows?.[workflowOriginId]?.agents ||
      state.agent_roles ||
      [];
    document.getElementById('workflowBoard').innerHTML = workflowDraft
      .map(
        (s, i) =>
          `<div class="node ${s.enabled ? '' : 'off'}" data-i="${i}" style="left:${s.x}px;top:${s.y}px" onpointerdown="startNodeDrag(event,${i})"><span class="port in"></span><span class="port out"></span><div class="node-header"><div class="node-icon">${iconFor(s.name)}</div><div><div class="node-title">${roleLabels[s.role] || esc(s.role)}</div><div class="muted" style="font-size:12px">${esc(s.name)}</div></div></div><div class="node-body"><label class="label">Agente de la etapa</label><select class="stage-agent" onclick="event.stopPropagation()" onchange="setNodeAgent(${i},this.value)"><option value="" ${!s.agent_id ? 'selected' : ''}>${esc(roleLabels[s.role] || s.role)} predeterminado</option>${candidates
            .filter((a) => (a.base_role || a.role) === s.role)
            .map(
              (a) =>
                `<option value="${a.role}" ${s.agent_id === a.role ? 'selected' : ''}>${esc(a.name || roleLabels[a.role] || a.role)} · ${esc(a.role)}</option>`,
            )
            .join(
              '',
            )}${s.agent_id && !candidates.some((a) => a.role === s.agent_id && (a.base_role || a.role) === s.role) ? `<option selected value="${esc(s.agent_id)}">${esc(s.agent_id)} · no disponible</option>` : ''}</select><label class="label">Perfil de modelo</label><select onclick="event.stopPropagation()" onchange="setNodeProfile(${i},this.value)"><option value="" ${!s.profile ? 'selected' : ''}>Usar agente</option><option value="rapido" ${s.profile === 'rapido' ? 'selected' : ''}>Rápido</option><option value="equilibrado" ${s.profile === 'equilibrado' ? 'selected' : ''}>Equilibrado</option><option value="potente" ${s.profile === 'potente' ? 'selected' : ''}>Potente</option></select><label class="label">Plataforma</label><select onclick="event.stopPropagation()" onchange="setNodeTool(${i},this.value)"><option value="" ${!s.tool ? 'selected' : ''}>Usar agente/predeterminada</option><option value="codex" ${s.tool === 'codex' ? 'selected' : ''}>Codex</option><option value="opencode" ${s.tool === 'opencode' ? 'selected' : ''}>OpenCode</option></select>${requiredStep(kind, s.name) ? '<div class="node-lock">Etapa obligatoria</div>' : `<label class="node-toggle" onclick="event.stopPropagation()"><input type="checkbox" ${s.enabled ? 'checked' : ''} onchange="toggleNode(${i},this.checked)"> etapa activa</label>`}<div class="node-meta"><span class="pill">${s.enabled ? 'activa' : 'apagada'}</span></div></div></div>`,
      )
      .join('');
    drawConnections();
  };
  window.setNodeAgent = function (i, v) {
    workflowDraft[i].agent_id = v || null;
    markDirty();
  };
  window.setNodeProfile = function (i, v) {
    workflowDraft[i].profile = v || null;
    markDirty();
  };
  const note = document.querySelector('#designer .workflow-note');
  if (note) {
    note.insertAdjacentHTML(
      'beforeend',
      '<div class="snapshot-note">Puedes editar este diseño en cualquier momento. Un flujo que ya haya arrancado conserva una snapshot propia y no cambia.</div>',
    );
  }
  applyTerminology();
})();

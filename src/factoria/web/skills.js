/* Project skill editor. No provider processes are started here. */
(function () {
  let skillDraft = null,
    skillProject = null,
    skillRevision = null,
    skillDirty = false,
    skillCreating = false,
    skillSaving = false;
  const nav = document.querySelector('.nav');
  const button = document.createElement('button');
  button.dataset.page = 'skills';
  button.textContent = 'Skills';
  nav.insertBefore(button, document.querySelector('.nav [data-page="agentRoles"]'));
  const section = document.createElement('section');
  section.id = 'skills';
  section.className = 'section';
  section.innerHTML =
    '<div class="concept-note"><strong>Skills del proyecto</strong><p>Guarda conocimiento e instrucciones reutilizables en Markdown. Después podrás asignarlas a tus agentes y preparar Codex y OpenCode.</p></div><button class="primary" id="newSkillButton" onclick="newSkill()">Crear skill</button><p id="skillStatus" role="status" aria-live="polite"></p><div id="skillList" class="agent-grid"></div><div id="skillEditor"></div>';
  document.querySelector('main.main').appendChild(section);
  button.onclick = () => {
    document.querySelectorAll('.nav button').forEach((x) => x.classList.remove('active'));
    document.querySelectorAll('.section').forEach((x) => x.classList.remove('active'));
    button.classList.add('active');
    section.classList.add('active');
    document.getElementById('title').textContent = 'Skills';
    renderSkills();
  };
  function status(message) {
    document.getElementById('skillStatus').textContent = message;
  }
  function canLeave() {
    return (
      !skillSaving && (!skillDirty || confirm('Hay cambios de skill sin guardar. ¿Descartarlos?'))
    );
  }
  window.hasUnsavedSkills = () => skillDirty || skillSaving;
  function reset() {
    skillDraft = null;
    skillDirty = false;
    skillRevision = null;
    skillProject = state.selected_project?.path || null;
    document.getElementById('skillEditor').innerHTML = '';
    status('');
  }
  function renderSkills() {
    const project = state.selected_project?.path || null;
    document.getElementById('newSkillButton').disabled =
      !project || skillSaving || !!state.skill_configuration_error;
    const picker = document.getElementById('agentSkillPicker');
    if (picker && state.skills)
      picker.innerHTML =
        '<option value="">Selecciona una skill…</option>' +
        state.skills.map((s) => `<option value="${esc(s.path)}">${esc(s.name)}</option>`).join('');
    if (skillDirty || skillSaving) {
      if (project !== skillProject)
        status(
          'Borrador de otro proyecto conservado. Vuelve al proyecto de origen o descarta / recarga.',
        );
      return;
    }
    if (project !== skillProject) reset();
    const list = document.getElementById('skillList');
    if (!project) {
      list.textContent = 'Selecciona un proyecto para gestionar sus skills.';
      return;
    }
    if (state.skill_configuration_error) {
      list.textContent = state.skill_configuration_error;
      return;
    }
    if (!state.skills) return;
    list.innerHTML =
      state.skills
        .map(
          (s) =>
            `<div class="agent-editor"><h3>${esc(s.name)}</h3><p>${esc(s.description)}</p><div class="muted">${esc(s.path)}</div><button class="secondary" onclick="editSkill('${s.id}')">Modificar</button></div>`,
        )
        .join('') ||
      '<p class="muted">Todavía no hay skills. Crea la primera para este proyecto.</p>';
    if (state.unmanaged_skill_files?.length) {
      const note = document.createElement('p');
      note.className = 'muted';
      note.textContent =
        'Archivos ajenos conservados: ' +
        state.unmanaged_skill_files.join(', ') +
        '. No se sobrescriben desde este editor.';
      list.appendChild(note);
    }
    if (skillDraft) {
      const current = state.skills.find((s) => s.id === skillDraft.id);
      if (current) {
        skillDraft = structuredClone(current);
        skillRevision = state.skill_catalog_revision;
        renderEditor();
      }
    }
  }
  window.newSkill = function () {
    if (
      !state.selected_project ||
      !state.skill_catalog_revision ||
      state.skill_configuration_error ||
      !canLeave()
    )
      return;
    skillProject = state.selected_project.path;
    skillRevision = state.skill_catalog_revision;
    skillCreating = true;
    skillDraft = { id: '', name: '', description: '', content: '' };
    skillDirty = true;
    renderEditor();
    status('Nueva skill · cambios sin guardar');
  };
  window.editSkill = function (id) {
    if (!canLeave() || state.skill_configuration_error) return;
    const source = state.skills?.find((s) => s.id === id);
    if (!source) return;
    skillDraft = structuredClone(source);
    skillProject = state.selected_project.path;
    skillRevision = state.skill_catalog_revision;
    skillCreating = false;
    skillDirty = false;
    renderEditor();
    status('Skill guardada');
  };
  function renderEditor() {
    const s = skillDraft;
    document.getElementById('skillEditor').innerHTML =
      `<div class="agent-editor" style="margin-top:16px"><fieldset id="skillFields" style="border:0;padding:0;margin:0"><h3>${skillCreating ? 'Crear skill' : 'Modificar skill'}</h3><label>Identificador<input id="skillId" maxlength="64" value="${esc(s.id)}" ${skillCreating ? '' : 'disabled'} placeholder="revision-api"></label><label>Nombre<input id="skillName" maxlength="120" value="${esc(s.name)}"></label><label>Descripción<textarea id="skillDescription" rows="2" maxlength="1000">${esc(s.description)}</textarea></label><label>Contenido Markdown<textarea id="skillContent" rows="16" maxlength="100000" spellcheck="false">${esc(s.content)}</textarea></label><div class="actions"><button class="primary" onclick="saveSkill()">Guardar skill</button><button class="secondary" onclick="discardSkill()">Descartar / recargar</button></div><p class="muted">Archivo: .factoria/skills/&lt;identificador&gt;.md. Tras guardar, asigna la skill a un agente y prepara la integración.</p></fieldset></div>`;
  }
  window.saveSkill = async function () {
    if (!skillDraft || skillSaving) return;
    if (skillProject !== state.selected_project?.path)
      return status('Vuelve al proyecto de origen del borrador antes de guardar.');
    const payload = {
      id: document.getElementById('skillId').value.trim(),
      name: document.getElementById('skillName').value.trim(),
      description: document.getElementById('skillDescription').value,
      content: document.getElementById('skillContent').value,
      revision: skillRevision,
      project_path: skillProject,
    };
    skillSaving = true;
    document.getElementById('skillFields').disabled = true;
    status('Guardando…');
    try {
      const result = await api(
        skillCreating ? '/api/skill/create' : '/api/skill/save',
        'POST',
        payload,
      );
      state = result.state;
      skillDraft = structuredClone(state.skills.find((s) => s.id === payload.id));
      skillRevision = state.skill_catalog_revision;
      skillDirty = false;
      skillCreating = false;
      status('Guardado. Prepara la integración para actualizar las herramientas.');
    } catch (e) {
      skillDirty = true;
      status(e.message + ' · Tu borrador se conserva.');
    } finally {
      skillSaving = false;
      document.getElementById('skillFields').disabled = false;
      if (!skillDirty) renderAll();
    }
  };
  window.discardSkill = async function () {
    if (!canLeave()) return;
    try {
      state = await api('/api/state');
      reset();
      renderAll();
      status('Catálogo recargado; cambios descartados');
    } catch (e) {
      status(e.message);
    }
  };
  window.assignCatalogSkill = function (path) {
    const input = document.getElementById('agent-skills');
    if (!path || !input || !state.skills?.some((s) => s.path === path)) return;
    const paths = input.value
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean);
    if (!paths.includes(path)) paths.push(path);
    input.value = paths.join('\n');
    input.dispatchEvent(new Event('input', { bubbles: true }));
  };
  document.getElementById('skillEditor').addEventListener('input', () => {
    skillDirty = true;
    status('Cambios sin guardar');
  });
  window.addEventListener('beforeunload', (event) => {
    if (skillDirty || skillSaving) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  for (const key of ['selectProject', 'createProject', 'saveProjectsRoot']) {
    const previous = window[key];
    window[key] = async function (...args) {
      if (!canLeave()) return;
      const before = state.selected_project?.path;
      const result = await previous(...args);
      if (before !== state.selected_project?.path) {
        reset();
        renderSkills();
      }
      return result;
    };
  }
  const previousRender = renderAll;
  renderAll = function () {
    previousRender();
    renderSkills();
  };
  renderSkills();
})();

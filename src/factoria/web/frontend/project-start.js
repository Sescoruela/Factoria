/* Project preparation and task handoff in the overview. */
const guide = { project: null, snapshot: null, busy: false, preview: null };
const taskTypes = new Map([
  ['fix', 'Corregir un problema'],
  ['feature', 'Añadir una funcionalidad'],
]);

function preparationContent(project, integration) {
  const conflicts = guide.preview?.integration?.conflicts?.length
    ? guide.preview.integration.conflicts
    : integration?.conflicts || [];
  if (conflicts.length) {
    return `<h3>Revisar qué impide continuar</h3>
      <p>Factoría encontró archivos editados fuera de la preparación. Revisa su contenido en el repositorio y conserva los cambios que necesites. Después, vuelve a comprobar el proyecto.</p>
      <ul class="guide-files">${conflicts.map((file) => `<li><code>${esc(file)}</code></li>`).join('')}</ul>
      <button type="button" class="primary" data-guide="refresh">Volver a comprobar</button>`;
  }
  if (integration?.error) {
    return `<h3>Revisar qué impide continuar</h3>
      <p>${esc(integration.error)}</p>
      <button type="button" class="primary" data-guide="refresh">Volver a comprobar</button>
      <button type="button" class="secondary" data-open-page="configuration">Abrir configuración</button>`;
  }
  const preview = guide.preview;
  if (!project.memory_initialized) {
    return `<h3>Preparar proyecto</h3>
      <p>Primero, Factoría propone una memoria con la estructura del repositorio y los comandos que detecta. Revisa la propuesta antes de guardarla.</p>
      ${preview?.memory ? `<pre class="guide-preview">${esc(preview.memory)}</pre>` : ''}
      <button type="button" class="primary" data-guide="${preview?.memory ? 'save-memory' : 'preview-memory'}">
        ${preview?.memory ? 'Guardar memoria' : 'Revisar memoria inicial'}
      </button>`;
  }
  if (!integration?.ready) {
    const files = preview?.integration?.changed || [];
    return `<h3>Preparar proyecto</h3>
      <p>Factoría prepara las instrucciones que usarán Codex y OpenCode. Revisa los archivos antes de aplicar los cambios.</p>
      ${files.length ? `<ul class="guide-files">${files.map((file) => `<li><code>${esc(file)}</code></li>`).join('')}</ul>` : ''}
      <button type="button" class="primary" data-guide="${files.length ? 'apply' : 'preview'}">
        ${files.length ? 'Aplicar los cambios revisados' : 'Ver archivos que cambiarán'}
      </button>`;
  }
  return '';
}

function taskContent(workflows, allowed) {
  if (!allowed.length)
    return '<h3>Proyecto listo</h3><p>La configuración del proyecto no permite iniciar ningún flujo.</p><button type="button" class="secondary" data-open-page="designer">Revisar workflows</button>';
  const tasks = [...taskTypes]
    .map(([kind, label]) => {
      const id = allowed.includes(kind) ? kind : allowed.find((id) => workflows[id]?.kind === kind);
      return id
        ? `<button type="button" class="primary" data-guide="task" data-kind="${esc(id)}">${label}</button>`
        : '';
    })
    .join('');
  return `<h3>¿Qué quieres hacer?</h3><div class="actions guide-actions">${tasks}</div>
    <form class="guide-form" id="guidedTaskForm" hidden>
      <div class="guide-fields">
        ${
          allowed.length > 2 || allowed.some((id) => !taskTypes.has(id))
            ? `<label>Workflow<select name="workflow">${allowed.map((id) => `<option value="${esc(id)}">${esc(taskTypes.get(id) || workflows[id]?.name || id)}</option>`).join('')}</select></label>`
            : '<input type="hidden" name="workflow">'
        }
        <label>Herramienta<select name="tool"><option value="codex">Codex</option><option value="opencode">OpenCode</option></select></label>
      </div>
      <label>Describe la tarea<textarea name="task" rows="3" required></textarea></label>
      <label>Petición para pegar<textarea name="request" rows="3" readonly></textarea></label>
      <p>Abre la herramienta en este repositorio y pega la petición.</p>
      <button type="submit" class="primary">Copiar petición</button>
    </form>`;
}

window.renderProjectOverview = function (container, project) {
  if (guide.project !== (project?.path ?? null)) {
    Object.assign(guide, {
      project: project?.path ?? null,
      snapshot: null,
      preview: null,
      busy: false,
      task: null,
    });
  }
  const integration = state.integration;
  const workflows = state.workflows || {};
  const allowed = integration?.enabled_workflows || [];
  const snapshot = JSON.stringify([
    project?.name,
    project?.branch,
    project?.dirty,
    project?.error,
    project?.memory_initialized,
    integration?.ready,
    integration?.conflicts,
    integration?.error,
    allowed,
    Object.entries(workflows).map(([id, workflow]) => [
      id,
      workflow.name,
      workflow.kind,
      workflow.steps?.length,
      workflow.error,
    ]),
    state.skills?.length,
    state.agent_roles?.length,
    state.skill_configuration_error,
    state.agent_configuration_error,
  ]);
  if (guide.busy || guide.snapshot === snapshot) return;
  guide.snapshot = snapshot;
  const advancedOpen = container.querySelector('#projectOptions')?.open;
  const graphOpen = container.querySelector('#projectMemoryGraph')?.open;
  if (!project) {
    container.innerHTML =
      '<article class="empty-workspace"><h2>¿En qué vas a trabajar?</h2><p>Elige el repositorio en el que quieres usar Factoría.</p><button type="button" class="primary" data-open-page="projects" data-start-selection>Elegir proyecto</button></article>';
    return;
  }
  if (project.error) {
    container.innerHTML = `<article class="empty-workspace"><h2>Hay que revisar este proyecto</h2><p>${esc(project.error)}</p><button type="button" class="secondary" data-open-page="configuration">Revisar configuración</button></article>`;
    return;
  }
  const rows = Object.entries(workflows)
    .map(
      ([id, workflow]) => `
    <button type="button" class="workflow-row" data-open-page="designer" data-workflow="${esc(id)}">
      <span><strong>${esc(workflow.name || taskTypes.get(id) || id)}</strong>
      <small>${workflow.error ? 'Revisar configuración' : `${workflow.steps?.length || 0} etapas`}</small></span>
      <span class="workflow-arrow" aria-hidden="true">↗</span>
    </button>`,
    )
    .join('');
  container.innerHTML = `<article class="project-overview">
    <div><h2>${esc(project.name)}</h2><div class="project-context"><span class="branch-name">${esc(project.branch || 'Sin rama')}</span><span>${project.dirty ? 'Hay cambios sin guardar en Git' : 'Sin cambios en Git'}</span></div></div>
    <button type="button" class="secondary" data-open-page="projects" data-start-selection>Cambiar proyecto</button>
  </article>
  <section class="card project-guide" aria-label="Empezar con este proyecto">
    ${preparationContent(project, integration) || taskContent(workflows, allowed)}
    ${project.dirty && project.memory_initialized && integration?.ready ? '<p class="guide-git-note">Revisa y guarda en Git la preparación que quieras conservar antes de empezar la tarea.</p>' : ''}
    <div class="guide-status" id="guideStatus" role="status"></div>
  </section>
  <details class="project-options" id="projectOptions" ${advancedOpen ? 'open' : ''}>
    <summary>Configuración del proyecto</summary>
    <div class="project-resources">
      <button type="button" data-open-page="skills">${state.skill_configuration_error ? 'Revisar skills' : `${state.skills?.length || 0} skill${state.skills?.length === 1 ? '' : 's'}`}</button>
      <button type="button" data-open-page="agentRoles">${state.agent_configuration_error ? 'Revisar agentes' : `${state.agent_roles?.length || 0} agente${state.agent_roles?.length === 1 ? '' : 's'}`}</button>
      <button type="button" data-open-page="relations">Ver relaciones</button>
      <button type="button" data-open-page="integration">Ver integración</button>
    </div>
    <h3>Workflows</h3><div class="workflow-list">${rows || '<p>No hay workflows disponibles.</p>'}</div>
    ${
      project.memory_initialized
        ? `<details id="projectMemoryGraph" ${graphOpen ? 'open' : ''}>
      <summary>Grafo de memoria</summary>
      <p>Genera un índice de la documentación del proyecto y busca decisiones o módulos por tema.</p>
      <form class="guide-form" id="guideGraphForm">
        <label>Qué buscar en la memoria<input name="query" maxlength="300"></label>
        <div class="actions guide-actions"><button type="submit" class="primary">Buscar en la memoria</button><button type="button" class="secondary" data-guide="build-graph">Generar índice</button></div>
      </form>
      <div id="guideGraphResult" role="status"></div>
    </details>`
        : ''
    }
  </details>`;
  bindProjectGuide(container, project);
};

function bindProjectGuide(container, project) {
  const panel = container.querySelector('.project-guide');
  const status = panel.querySelector('#guideStatus');
  const form = panel.querySelector('#guidedTaskForm');
  const task = (guide.task ??= {
    kind: '',
    description: '',
    tool: state.default_tool === 'opencode' ? 'opencode' : 'codex',
  });
  const graphForm = container.querySelector('#guideGraphForm');
  const graphResult = container.querySelector('#guideGraphResult');
  const sameProject = () => state.selected_project?.path === project.path;
  function updateRequest() {
    const fields = form.elements;
    Object.assign(task, {
      kind: fields.workflow.value,
      description: fields.task.value,
      tool: fields.tool.value,
    });
    const command = task.tool === 'opencode' ? '/' : '$';
    fields.request.value =
      task.kind && task.description.trim()
        ? `${command}factoria-${task.kind} ${task.description.trim()}`
        : '';
  }
  if (form) {
    form.elements.tool.value = task.tool;
    form.elements.task.value = task.description;
    if (task.kind && state.integration?.enabled_workflows.includes(task.kind)) {
      form.elements.workflow.value = task.kind;
      form.hidden = false;
      updateRequest();
    }
    form.oninput = updateRequest;
    form.onsubmit = async (event) => {
      event.preventDefault();
      updateRequest();
      if (!form.elements.request.value) {
        status.textContent = 'Describe la tarea para copiar la petición.';
        form.elements.task.focus();
        return;
      }
      try {
        await navigator.clipboard.writeText(form.elements.request.value);
        status.textContent = 'Petición copiada.';
      } catch {
        form.elements.request.focus();
        form.elements.request.select();
        status.textContent = 'La petición está seleccionada. Pulsa Ctrl+C para copiarla.';
      }
    };
  }
  async function run(action) {
    if (guide.busy) return;
    if (
      window.hasUnsavedProjectChanges?.() &&
      !['refresh', 'recall', 'build-graph'].includes(action)
    ) {
      status.textContent =
        'Guarda o descarta los cambios de configuración antes de preparar el proyecto.';
      return;
    }
    const buttons = [...container.querySelectorAll('[data-guide], form button')];
    const graphAction = ['recall', 'build-graph'].includes(action);
    const output = graphAction ? graphResult : status;
    guide.busy = true;
    buttons.forEach((button) => (button.disabled = true));
    output.textContent = 'Comprobando…';
    let nextState;
    let redraw = false;
    try {
      if (action === 'refresh') {
        nextState = await api('/api/state');
        if (sameProject()) guide.preview = null;
      } else if (graphAction) {
        const query = graphForm.elements.query.value.trim();
        if (action === 'recall' && !query) throw new Error('Escribe un tema para buscar.');
        const graph = await api('/api/project/memory-graph', 'POST', {
          project_path: project.path,
          action: action === 'recall' ? 'recall' : 'build',
          query,
        });
        if (!sameProject()) return;
        graphResult.innerHTML =
          action === 'build-graph'
            ? `<p>Índice actualizado con ${graph.nodes} elementos y ${graph.edges} relaciones.</p>`
            : graph.matches.length
              ? `<ul class="guide-files">${[...graph.matches, ...graph.related].map((node) => `<li><strong>${esc(node.label)}</strong>${node.source ? ` <code>${esc(node.source)}${node.line ? `:${node.line}` : ''}</code>` : ''}${node.excerpt ? `<p>${esc(node.excerpt)}</p>` : ''}</li>`).join('')}</ul>`
              : '<p>No se encontraron coincidencias.</p>';
        return;
      } else if (action === 'preview-memory' || action === 'save-memory') {
        const save = action === 'save-memory';
        const args = ['memoria-init', '--name', project.name, ...(save ? ['--yes'] : [])];
        const result = await api('/api/command', 'POST', { project_path: project.path, args });
        if (!sameProject()) return;
        if (!result.ok) throw new Error(result.output.trim() || 'No se pudo preparar la memoria.');
        guide.preview = save ? null : { memory: result.output };
        nextState = result.state;
      } else {
        const confirmed = action === 'apply';
        const result = await api('/api/project/prepare', 'POST', {
          project_path: project.path,
          confirmed,
          revision: guide.preview?.integration?.revision,
        });
        if (!sameProject()) return;
        guide.preview = confirmed ? null : { integration: result };
        nextState = result.state;
      }
      redraw = sameProject();
      if (redraw) state = nextState;
    } catch (error) {
      if (sameProject()) {
        if (action === 'apply') {
          guide.preview = null;
          guide.snapshot = null;
          guide.busy = false;
          renderAll();
          container.querySelector('#guideStatus').textContent = error.message;
        } else output.textContent = error.message;
      }
    } finally {
      if (sameProject()) guide.busy = false;
      buttons.forEach((button) => (button.disabled = false));
      if (redraw) {
        guide.snapshot = null;
        renderAll();
        const current = container.querySelector('.project-guide');
        const next = current?.querySelector('[data-guide]');
        next?.focus({ preventScroll: true });
        if (action === 'apply' && state.integration?.ready)
          current.querySelector('#guideStatus').textContent = 'Proyecto preparado.';
      }
    }
  }
  container.onclick = (event) => {
    const button = event.target.closest('[data-guide]');
    if (!button || button.disabled) return;
    const action = button.dataset.guide;
    if (action === 'task') {
      form.hidden = false;
      form.elements.workflow.value = button.dataset.kind;
      updateRequest();
      form.elements.task.focus();
    } else run(action);
  };
  if (graphForm)
    graphForm.onsubmit = (event) => {
      event.preventDefault();
      run('recall');
    };
}

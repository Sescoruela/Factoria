/* Presentation only: real project state, clear navigation, no persistence or provider calls. */
window.openProjectSection = function (page, workflow) {
  if (workflow && window.hasUnsavedProjectChanges())
    return toast('Guarda o descarta los cambios pendientes antes de abrir otro workflow.');
  const button = document.querySelector(`.nav [data-page="${page}"]`);
  if (!button) {
    if (!['skills', 'agentRoles', 'integration'].includes(page)) return;
    if (window.hasUnsavedProjectChanges())
      return toast('Guarda o descarta los cambios pendientes antes de abrir el editor.');
    const destination = new URL('/editors', location.href);
    destination.searchParams.set('token', token);
    destination.hash = 'page=' + encodeURIComponent(page);
    location.assign(destination.href);
    return;
  }
  button.click();
  if (workflow && document.getElementById('workflowKind').value !== workflow) {
    document.getElementById('workflowKind').value = workflow;
    changeWorkflowKind();
  }
};
window.renderProjectOverview = function (container, project) {
  if (!project) {
    container.innerHTML =
      '<article class="empty-workspace"><p class="eyebrow">Empieza por un proyecto</p><h2>¿En qué vas a trabajar?</h2><p>Abre un repositorio para organizar sus skills, agentes y workflows. Su configuración se guarda junto al código.</p><button class="primary" data-open-page="projects">Elegir proyecto</button></article>';
    return;
  }
  if (project.error) {
    container.innerHTML = `<article class="empty-workspace"><h2>Hay que revisar este proyecto</h2><p>${esc(project.error)}</p><button class="secondary" data-open-page="configuration">Revisar configuración</button></article>`;
    return;
  }
  const workflows = Object.entries(state.workflows || {});
  const ready = state.integration?.ready === true;
  const rows = workflows
    .map(
      ([id, workflow], index) =>
        `<button class="workflow-row" data-open-page="designer" data-workflow="${esc(id)}"><span class="workflow-number" aria-hidden="true">${String(index + 1).padStart(2, '0')}</span><span><strong>${esc(workflow.name || (id === 'feature' ? 'Nueva funcionalidad' : id === 'fix' ? 'Corregir un problema' : id))}</strong><small>${workflow.error ? 'Revisar configuración' : `${workflow.steps?.length || 0} etapas · ${workflow.kind === 'fix' ? 'Corrección' : 'Desarrollo'}`}</small></span><span class="workflow-arrow" aria-hidden="true"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 19L19 5M5 5h14v14"/></svg></span></button>`,
    )
    .join('');
  container.innerHTML = `<article class="project-overview"><div><p class="eyebrow">Proyecto actual</p><h2>${esc(project.name)}</h2><div class="project-context"><span class="branch-name">${esc(project.branch || 'Sin rama')}</span><span>${project.dirty ? 'Hay cambios sin guardar en Git' : 'Sin cambios en Git'}</span></div></div><div class="actions"><button class="primary" data-open-page="designer">Ver workflows</button><button class="secondary" data-open-page="integration">Preparar proyecto</button></div></article><div class="overview-layout"><section><div class="section-heading"><h3>Workflows disponibles</h3><span>${workflows.length} en este proyecto</span></div><div class="workflow-list">${rows || '<div class="item">No se ha podido cargar el catálogo.</div>'}</div><div class="project-resources"><button data-open-page="skills">${state.skill_configuration_error ? 'Revisar skills' : `${state.skills?.length || 0} ${(state.skills?.length || 0) === 1 ? 'skill' : 'skills'}`}</button><button data-open-page="agentRoles">${state.agent_configuration_error ? 'Revisar agentes' : `${state.agent_roles?.length || 0} ${(state.agent_roles?.length || 0) === 1 ? 'agente' : 'agentes'}`}</button><button data-open-page="relations">Ver relaciones</button></div></section><aside class="readiness"><h3>Antes de trabajar</h3><p>Comprueba el contexto que usarán tus herramientas.</p><div class="readiness-item"><strong>Memoria del proyecto</strong><p>${project.memory_initialized ? 'Inicializada en este repositorio.' : 'Pendiente de inicializar.'}</p>${project.memory_initialized ? '' : '<button class="secondary" onclick="initMemory()">Inicializar memoria</button>'}</div><div class="readiness-item"><strong>Integración</strong><p>${ready ? 'La configuración está preparada y actualizada.' : state.integration?.error ? esc(state.integration.error) : 'Prepara los archivos para Codex y OpenCode.'}</p><button class="secondary" data-open-page="integration">${ready ? 'Revisar integración' : 'Revisar y preparar'}</button></div><div class="readiness-item"><strong>Trabajo con IA</strong><p>Abre Codex u OpenCode en este proyecto cuando quieras empezar.</p></div><div class="readiness-item"><strong>Revisión de seguridad</strong><p>${project.security?.finding_count != null ? `${project.security.finding_count} hallazgos registrados.` : 'No hay una revisión disponible.'}</p><button class="secondary" data-open-page="security">Ver revisión</button></div></aside></div>`;
};
(function () {
  function setup() {
    const nav = document.querySelector('.nav'),
      sidebar = document.querySelector('.sidebar');
    if (!nav || !sidebar) return;
    const icons = {
      dashboard:
        '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
      projects: '<path d="M3 7h7l2-3h9v16H3z"/>',
      skills: '<path d="M5 3h14v18H5zM8 8h8M8 12h8M8 16h5"/>',
      agentRoles: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-3a8 8 0 0116 0v3"/>',
      designer:
        '<rect x="2" y="8" width="5" height="8" rx="1"/><rect x="17" y="8" width="5" height="8" rx="1"/><path d="M7 12h10M11 8l4 4-4 4"/>',
      relations:
        '<circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="12" cy="19" r="2"/><path d="M7 5h10M6 7l5 10M18 7l-5 10"/>',
      integration: '<path d="M8 4v6m8-6v6M5 10h14v3a7 7 0 01-14 0zM12 20v2"/>',
      history: '<path d="M3 11a9 9 0 119 10M3 4v7h7M12 7v5l4 2"/>',
      templates: '<rect x="7" y="7" width="14" height="14" rx="1"/><path d="M3 17V3h14"/>',
      resources: '<path d="M3 4h18v5H3zM5 9v12h14V9M10 13h4"/>',
      configuration:
        '<path d="M3 7h18M3 17h18"/><circle cx="8" cy="7" r="3"/><circle cx="16" cy="17" r="3"/>',
      agents: '<rect x="3" y="3" width="18" height="13" rx="1"/><path d="M8 21h8M12 16v5"/>',
      security: '<path d="M12 2l8 4v6c0 5-8 10-8 10S4 17 4 12V6zM8 12l3 3 5-6"/>',
      commands: '<path d="M4 6l6 6-6 6M13 18h7"/>',
      flows: '<path d="M8 4l12 8-12 8z"/>',
    };
    const groups = [
      ['Proyecto', ['dashboard', 'projects']],
      ['Configurar', ['skills', 'agentRoles', 'designer', 'relations']],
      ['Trabajar', ['integration', 'flows', 'history']],
      [
        'Herramientas',
        ['templates', 'resources', 'configuration', 'agents', 'security', 'commands'],
      ],
    ];
    nav.id = 'primaryNavigation';
    nav.setAttribute('aria-label', 'Navegación principal');
    nav.setAttribute('role', 'navigation');
    for (const [label, pages] of groups) {
      const group = document.createElement('div');
      group.className = 'nav-group';
      group.setAttribute('role', 'group');
      group.setAttribute('aria-label', label);
      const heading = document.createElement('span');
      heading.className = 'nav-group-label';
      heading.textContent = label;
      group.appendChild(heading);
      for (const page of pages) {
        const button = nav.querySelector(`[data-page="${page}"]`);
        if (!button) continue;
        const label =
          page === 'dashboard'
            ? 'Resumen'
            : page === 'designer'
              ? 'Workflows'
              : page === 'agents'
                ? 'Codex y OpenCode'
                : page === 'resources'
                  ? 'Archivo de recursos'
                  : button.textContent;
        button.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[page] || ''}</svg><span>${esc(label)}</span>`;
        group.appendChild(button);
      }
      if (group.querySelector('button')) nav.appendChild(group);
    }
    const toggle = document.createElement('button');
    toggle.id = 'navToggle';
    toggle.className = 'nav-toggle';
    toggle.type = 'button';
    toggle.textContent = 'Menú';
    toggle.setAttribute('aria-controls', nav.id);
    toggle.setAttribute('aria-expanded', 'false');
    toggle.onclick = () => {
      const open = sidebar.classList.toggle('menu-open');
      toggle.setAttribute('aria-expanded', String(open));
    };
    sidebar.insertBefore(toggle, nav);
    const note = document.createElement('p');
    note.className = 'sidebar-note';
    note.textContent = 'Codex y OpenCode se abren por separado.';
    sidebar.appendChild(note);
    const updateCurrent = () =>
      nav
        .querySelectorAll('button')
        .forEach((button) =>
          button.classList.contains('active')
            ? button.setAttribute('aria-current', 'page')
            : button.removeAttribute('aria-current'),
        );
    new MutationObserver(updateCurrent).observe(nav, {
      subtree: true,
      attributes: true,
      attributeFilter: ['class'],
    });
    updateCurrent();
    nav.addEventListener('click', (event) => {
      if (event.target.closest('button')) {
        sidebar.classList.remove('menu-open');
        toggle.setAttribute('aria-expanded', 'false');
        if (window.matchMedia('(max-width: 800px)').matches)
          document.querySelector('.main').focus({ preventScroll: true });
      }
    });
    document.addEventListener('click', (event) => {
      const button = event.target.closest('[data-open-page]');
      if (button) openProjectSection(button.dataset.openPage, button.dataset.workflow);
    });
    const labels = {
      projectsRootInput: 'Carpeta de proyectos',
      projectSearch: 'Buscar proyectos',
      newName: 'Nombre del nuevo proyecto',
      newPurpose: 'Descripción del nuevo proyecto',
      workflowKind: 'Workflow seleccionado',
      workflowTemplate: 'Workflow de partida',
      configAction: 'Operación de recuperación',
      configBackup: 'Copia de configuración',
      commandInput: 'Comando de Factoria',
    };
    for (const [id, label] of Object.entries(labels))
      document.getElementById(id)?.setAttribute('aria-label', label);
    document.getElementById('toast')?.setAttribute('role', 'status');
    const main = document.querySelector('.main');
    main.id = 'mainContent';
    main.tabIndex = -1;
    const skip = document.createElement('a');
    skip.href = '#mainContent';
    skip.className = 'skip-link';
    skip.textContent = 'Ir al contenido';
    document.body.prepend(skip);
    const requested = new URLSearchParams(location.hash.slice(1)).get('page');
    if (groups.some(([, pages]) => pages.includes(requested)))
      nav.querySelector(`[data-page="${requested}"]`)?.click();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setup);
  else setup();
})();

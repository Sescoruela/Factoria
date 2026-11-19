/* Presentation only: real project state, clear navigation, no persistence or provider calls. */
const fullEditorPages = new Set(['skills', 'agentRoles', 'integration']);
window.openProjectSection = function (page, workflow) {
  if (workflow && window.hasUnsavedProjectChanges())
    return toast('Guarda o descarta los cambios pendientes antes de abrir otro workflow.');
  const button = document.querySelector(`.nav [data-page="${page}"]`);
  if (!button) {
    if (!fullEditorPages.has(page)) return;
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
let choosingProjectFromOverview = false;
window.returnToProjectOverview = function () {
  if (choosingProjectFromOverview) {
    choosingProjectFromOverview = false;
    openProjectSection('dashboard');
  }
};
(function () {
  const pageLabels = {
    dashboard: 'Inicio',
    projects: 'Proyectos',
    integration: 'Preparar proyecto',
    designer: 'Workflows',
    agentRoles: 'Agentes',
    skills: 'Skills',
    relations: 'Relaciones',
    templates: 'Plantillas',
    resources: 'Archivo de recursos',
    flows: 'Ejecuciones',
    history: 'Historial',
    agents: 'Codex y OpenCode',
    configuration: 'Copias y recuperación',
    security: 'Seguridad',
    commands: 'Consola',
  };
  const navigation = [
    ['dashboard', null, '<path d="M3 10l9-7 9 7v10H3zM9 20v-6h6v6"/>'],
    ['projects', null, '<path d="M3 7h7l2-3h9v16H3z"/>'],
    ['Trabajo', 'work', '<path d="M8 4l12 8-12 8z"/>', ['flows', 'history']],
    [
      'Configurar proyecto',
      'project-settings',
      '<path d="M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-5 0v6"/>',
      [
        'integration',
        'designer',
        'agentRoles',
        'skills',
        'memory',
        'relations',
        'templates',
        'resources',
      ],
    ],
    [
      'Herramientas',
      'tools',
      '<path d="M13 6a5 5 0 0 0 5 6l3 3-5 5-3-3a5 5 0 0 0-6-5L3 8l4-4 4 4z"/>',
      ['agents', 'configuration', 'security', 'commands'],
    ],
  ];
  const chevron = '<path d="m8 10 4 4 4-4"/>';

  function setLabel(button, label, icon = '', expand = false) {
    const svg = (path, className = '') =>
      `<svg class="${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
    button.innerHTML = `${icon ? svg(icon) : ''}<span>${esc(label)}</span>${expand ? svg(chevron, 'nav-chevron') : ''}`;
  }

  function setGroupExpanded(group, expanded) {
    group.firstElementChild.setAttribute('aria-expanded', String(expanded));
    group.lastElementChild.hidden = !expanded;
  }

  function setup() {
    const nav = document.querySelector('.nav');
    const sidebar = document.querySelector('.sidebar');
    if (!nav || !sidebar) return;

    const existing = new Map(
      [...nav.querySelectorAll('[data-page]')].map((button) => [button.dataset.page, button]),
    );
    const routes = new Map();
    function pageButton(page, icon) {
      let button = existing.get(page);
      let label = pageLabels[page];
      if (!button && (fullEditorPages.has(page) || page === 'memory')) {
        button = document.createElement('button');
        button.dataset.openPage = page === 'memory' ? 'dashboard' : page;
        if (page === 'memory') {
          label = 'Memoria del proyecto';
          button.dataset.openMemory = '';
        }
      }
      if (!button) return null;
      button.type = 'button';
      setLabel(button, label, icon);
      if (page !== 'memory') routes.set(page, button);
      return button;
    }

    nav.id = 'primaryNavigation';
    nav.setAttribute('aria-label', 'Navegación principal');
    nav.setAttribute('role', 'navigation');
    const items = document.createDocumentFragment();
    for (const [labelOrPage, id, icon, pages] of navigation) {
      if (!pages) {
        const button = pageButton(labelOrPage, icon);
        if (button) items.appendChild(button);
        continue;
      }
      const group = document.createElement('div');
      group.className = 'nav-group';
      const trigger = document.createElement('button');
      trigger.type = 'button';
      trigger.className = 'nav-group-toggle';
      trigger.id = `nav-label-${id}`;
      const links = document.createElement('div');
      links.id = `nav-${id}`;
      links.className = 'nav-links';
      links.setAttribute('role', 'group');
      links.setAttribute('aria-labelledby', trigger.id);
      trigger.setAttribute('aria-controls', links.id);
      setLabel(trigger, labelOrPage, icon, true);
      for (const page of pages) {
        const button = pageButton(page);
        if (button) links.appendChild(button);
      }
      group.append(trigger, links);
      setGroupExpanded(group, false);
      trigger.onclick = () => setGroupExpanded(group, links.hidden);
      if (links.childElementCount) items.appendChild(group);
    }
    nav.replaceChildren(items);

    const toggle = document.createElement('button');
    toggle.id = 'navToggle';
    toggle.type = 'button';
    toggle.className = 'nav-toggle';
    toggle.textContent = 'Menú';
    toggle.setAttribute('aria-controls', nav.id);
    function setMenuExpanded(expanded) {
      sidebar.classList.toggle('menu-open', expanded);
      toggle.setAttribute('aria-expanded', String(expanded));
    }
    setMenuExpanded(false);
    toggle.onclick = () => setMenuExpanded(!sidebar.classList.contains('menu-open'));
    sidebar.insertBefore(toggle, nav);

    function updateCurrent() {
      const active = nav.querySelector('[data-page].active');
      for (const button of existing.values()) {
        if (button === active) button.setAttribute('aria-current', 'page');
        else button.removeAttribute('aria-current');
      }
      if (active) {
        document.getElementById('title').textContent = pageLabels[active.dataset.page];
        const group = active.closest('.nav-group');
        if (group) setGroupExpanded(group, true);
      }
    }
    new MutationObserver(updateCurrent).observe(nav, {
      subtree: true,
      attributes: true,
      attributeFilter: ['class'],
    });
    updateCurrent();

    const main = document.querySelector('.main');
    function finishNavigation() {
      setMenuExpanded(false);
      if (window.matchMedia('(max-width: 800px)').matches) main.focus({ preventScroll: true });
    }
    nav.addEventListener('click', (event) => {
      const page = event.target.closest('[data-page]');
      if (page?.classList.contains('active')) finishNavigation();
    });
    sidebar.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && sidebar.classList.contains('menu-open')) {
        setMenuExpanded(false);
        toggle.focus();
      }
    });
    document.addEventListener('click', (event) => {
      const button = event.target.closest('[data-open-page]');
      if (!button) return;
      choosingProjectFromOverview = button.hasAttribute('data-start-selection');
      openProjectSection(button.dataset.openPage, button.dataset.workflow);
      if (button.hasAttribute('data-open-memory')) {
        const graph = document.getElementById('projectMemoryGraph');
        if (graph && document.getElementById('dashboard').classList.contains('active')) {
          document.getElementById('projectOptions').open = true;
          graph.open = true;
          graph.querySelector('summary').focus();
        } else if (!graph) {
          toast('Primero prepara la memoria del proyecto desde Inicio.');
        }
      }
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
    main.id = 'mainContent';
    main.tabIndex = -1;
    const skip = document.createElement('a');
    skip.href = '#mainContent';
    skip.className = 'skip-link';
    skip.textContent = 'Ir al contenido';
    document.body.prepend(skip);
    const requested = new URLSearchParams(location.hash.slice(1)).get('page');
    routes.get(requested)?.click();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setup);
  else setup();
})();

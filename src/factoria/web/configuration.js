/* Explicit configuration recovery. No automatic migrations, provider calls or draft replacement. */
(function () {
  const nav = document.querySelector('.nav'),
    main = document.querySelector('main.main');
  if (!nav || !main) return;
  const section = document.createElement('section');
  section.id = 'configuration';
  section.className = 'section';
  section.innerHTML =
    '<div class="card"><h2>Configuración y recuperación</h2><p>Revisa los archivos antes de migrar o restaurar. Las copias son locales al repositorio y no incluyen snapshots, historial, memoria ni credenciales.</p><button id="configReload">Actualizar copias</button><select id="configAction"><option value="migrate">Migrar al esquema actual</option><option value="snapshot">Crear copia de configuración</option><option value="restore">Restaurar copia</option></select><select id="configBackup"></select><button id="configPreview">Revisar operación</button><button id="configApply" disabled>Confirmar y aplicar</button><p id="configStatus" role="status"></p><pre id="configDetails"></pre></div>';
  main.appendChild(section);
  const button = document.createElement('button');
  button.dataset.page = 'configuration';
  button.textContent = 'Recuperación';
  nav.appendChild(button);
  const el = (id) => document.getElementById(id),
    project = () => state.selected_project?.path || null;
  let plan = null,
    busy = false;
  function dirty() {
    return (
      window.hasUnsavedAgents?.() || window.hasUnsavedSkills?.() || workflowDirty || workflowSaving
    );
  }
  function invalidate() {
    plan = null;
    el('configApply').disabled = true;
  }
  function details(data) {
    el('configDetails').textContent = JSON.stringify(data, null, 2);
  }
  async function action(fn) {
    if (busy) return;
    busy = true;
    try {
      await fn();
    } catch (e) {
      el('configStatus').textContent = e.message;
      invalidate();
    } finally {
      busy = false;
    }
  }
  async function reload() {
    invalidate();
    const selected = project();
    const data = await api('/api/config/status', 'POST', { project_path: selected });
    if (project() !== selected) throw Error('El proyecto cambió');
    el('configBackup').replaceChildren();
    for (const backup of data.backups) {
      const option = document.createElement('option');
      option.value = backup.id;
      option.textContent = `${backup.id} · ${backup.kind} · ${backup.state}`;
      el('configBackup').appendChild(option);
    }
    details(data);
    el('configStatus').textContent =
      data.error || 'Copias actualizadas. Revisa una operación antes de aplicarla.';
  }
  button.onclick = () => {
    document.querySelectorAll('.nav button,.section').forEach((x) => x.classList.remove('active'));
    button.classList.add('active');
    section.classList.add('active');
    document.getElementById('title').textContent = 'Recuperación';
    action(reload);
  };
  for (const id of ['configAction', 'configBackup']) el(id).onchange = invalidate;
  el('configReload').onclick = () => action(reload);
  el('configPreview').onclick = () =>
    action(async () => {
      invalidate();
      if (dirty())
        throw Error(
          'Guarda o descarta explícitamente los borradores antes de recuperar configuración.',
        );
      const request = {
        project_path: project(),
        action: el('configAction').value,
        backup_id: el('configAction').value === 'restore' ? el('configBackup').value : null,
      };
      const data = await api('/api/config/preview', 'POST', request);
      if (
        dirty() ||
        project() !== request.project_path ||
        request.action !== el('configAction').value ||
        (request.action === 'restore' && request.backup_id !== el('configBackup').value)
      )
        throw Error('Cambió el proyecto o apareció un borrador.');
      plan = { request, token: data.token };
      details(data);
      el('configApply').disabled = !!data.conflicts.length;
      el('configStatus').textContent = data.conflicts.length
        ? 'Resolver conflictos antes de aplicar.'
        : 'Preview listo. La restauración sustituye o elimina únicamente los archivos mostrados.';
    });
  el('configApply').onclick = () =>
    action(async () => {
      if (!plan || dirty() || project() !== plan.request.project_path)
        throw Error('Revisa de nuevo el proyecto y sus borradores.');
      if (
        !confirm(
          '¿Aplicar los cambios revisados? Se crea o conserva una copia recuperable antes de escribir.',
        )
      )
        return;
      const selected = plan.request.project_path;
      const result = await api('/api/config/apply', 'POST', {
        ...plan.request,
        token: plan.token,
        confirmed: true,
      });
      invalidate();
      if (project() !== selected)
        throw Error('Operación terminada en el proyecto original; actualizar su vista.');
      details(result);
      el('configStatus').textContent =
        'Operación completada. Actualiza la aplicación para recargar los editores.';
    });
})();

/* Reversible project resource lifecycle; never launches a provider. */
(function () {
  const nav = document.querySelector('.nav'),
    main = document.querySelector('main.main');
  if (!nav || !main) return;
  let reviewed = null,
    busy = false;
  const section = document.createElement('section');
  section.id = 'resources';
  section.className = 'section';
  section.innerHTML =
    '<div class="card"><h2>Duplicar y archivar recursos</h2><p>Archivar conserva una copia y reserva el identificador. Retira primero las referencias activas. Los básicos solo se duplican. Las snapshots existentes se conservan.</p><button id="resourceReload">Recargar recursos</button><label>Operación<select id="resourceAction"><option value="duplicate">Duplicar</option><option value="archive">Archivar</option><option value="restore">Restaurar</option></select></label><label>Recurso<select id="resourceSource"></select></label><div id="resourceCopyFields"><label>Identificador nuevo<input id="resourceNewId" maxlength="64"></label><label>Nombre de la copia<input id="resourceName" maxlength="120"></label></div><div class="actions"><button id="resourcePreview">Ver impacto</button><button id="resourceApply" disabled>Confirmar operación revisada</button></div><pre id="resourceResult" role="status" aria-live="polite"></pre><h3>Registro de operaciones</h3><pre id="resourceHistory"></pre><p>Tras aplicar, revisa el diff y prepara ambas herramientas. No se cambia la configuración de proveedores.</p></div>';
  main.appendChild(section);
  const button = document.createElement('button');
  button.textContent = 'Archivo de recursos';
  button.dataset.page = 'resources';
  nav.appendChild(button);
  const el = (id) => document.getElementById(id),
    project = () => state.selected_project?.path || null;
  function invalidate() {
    reviewed = null;
    el('resourceApply').disabled = true;
  }
  function request() {
    const value = JSON.parse(el('resourceSource').value || 'null');
    if (!value) throw new Error('Selecciona un recurso');
    const action = el('resourceAction').value;
    const result = { action, kind: value.kind };
    result[action === 'restore' ? 'archive_id' : 'id'] =
      action === 'restore' ? value.archive_id : value.id;
    if (action === 'duplicate') {
      result.new_id = el('resourceNewId').value.trim();
      if (el('resourceName').value) result.name = el('resourceName').value;
    }
    return result;
  }
  async function action(work) {
    if (busy) return;
    if (!project()) return (el('resourceResult').textContent = 'Selecciona un proyecto');
    if (
      window.hasUnsavedSkills?.() ||
      window.hasUnsavedAgents?.() ||
      (typeof agentEdits !== 'undefined' && agentEdits) ||
      (typeof workflowDirty !== 'undefined' && workflowDirty)
    )
      return (el('resourceResult').textContent =
        'Guarda o descarta los borradores antes de continuar');
    busy = true;
    el('resourceApply').disabled = true;
    try {
      await work();
    } catch (error) {
      invalidate();
      el('resourceResult').textContent = error.message;
    } finally {
      busy = false;
    }
  }
  async function reload() {
    invalidate();
    const selected = project(),
      data = await api('/api/resource/list', 'POST', { project_path: selected });
    if (project() !== selected) throw new Error('El proyecto cambió; recarga los recursos');
    const restoring = el('resourceAction').value === 'restore';
    const entries = restoring ? data.history.filter((x) => x.status === 'archived') : data.active;
    const select = el('resourceSource');
    select.replaceChildren();
    for (const item of entries) {
      const option = document.createElement('option');
      option.value = JSON.stringify(item);
      option.textContent = `${item.kind} · ${item.id}${item.name ? ' · ' + item.name : ''}`;
      select.appendChild(option);
    }
    select.dataset.project = selected;
    el('resourceCopyFields').style.display =
      el('resourceAction').value === 'duplicate' ? '' : 'none';
    el('resourceHistory').textContent = JSON.stringify(data.history, null, 2);
  }
  button.onclick = () => {
    document.querySelectorAll('.nav button,.section').forEach((x) => x.classList.remove('active'));
    button.classList.add('active');
    section.classList.add('active');
    const title = el('title');
    if (title) title.textContent = 'Archivo de recursos';
    action(reload);
  };
  el('resourceReload').onclick = () => action(reload);
  el('resourceAction').onchange = () => action(reload);
  for (const id of ['resourceSource', 'resourceNewId', 'resourceName'])
    el(id).addEventListener('input', invalidate);
  el('resourcePreview').onclick = () =>
    action(async () => {
      if (el('resourceSource').dataset.project !== project())
        throw new Error('Recarga los recursos de este proyecto');
      const selected = project(),
        payload = request();
      const data = await api('/api/resource/preview', 'POST', {
        project_path: selected,
        request: payload,
      });
      if (project() !== selected || JSON.stringify(request()) !== JSON.stringify(payload))
        throw new Error('La selección cambió; revisa de nuevo');
      reviewed = { project: selected, request: payload, token: data.token };
      el('resourceResult').textContent = JSON.stringify(data, null, 2);
      el('resourceApply').disabled = !!data.blockers.length;
    });
  el('resourceApply').onclick = () =>
    action(async () => {
      const checked = reviewed;
      if (
        !checked ||
        checked.project !== project() ||
        JSON.stringify(checked.request) !== JSON.stringify(request())
      )
        throw new Error('Vuelve a revisar impacto');
      if (!confirm('¿Confirmar la operación y el impacto revisados?')) {
        el('resourceApply').disabled = false;
        return;
      }
      const result = await api('/api/resource/apply', 'POST', {
        project_path: checked.project,
        request: checked.request,
        token: checked.token,
        confirmed: true,
      });
      invalidate();
      el('resourceResult').textContent = JSON.stringify(result, null, 2);
      if (typeof refresh === 'function') await refresh();
      await reload();
    });
})();

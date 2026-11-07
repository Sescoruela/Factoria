/* Portable project templates. No provider execution or implicit integration. */
(function () {
  const nav = document.querySelector('.nav'),
    main = document.querySelector('main.main');
  if (!nav || !main) return;
  let preview = null,
    busy = false;
  const section = document.createElement('section');
  section.id = 'templates';
  section.className = 'section';
  section.innerHTML =
    '<div class="card"><h2>Plantillas entre proyectos</h2><p>Exporta la configuración guardada de skills, agentes y workflows. Revisa el contenido antes de compartirlo: el detector de secretos no garantiza encontrar todos los datos privados. No incluye memoria, políticas, comandos ni preferencias de máquina.</p><label>Nombre de plantilla<input id="templateName" maxlength="120" value="Mi plantilla"></label><div class="actions"><button id="templateExport">Exportar proyecto</button><button id="templateDownload" disabled>Descargar JSON</button></div><label>Abrir plantilla JSON<input id="templateFile" type="file" accept="application/json,.json"></label><label>Contenido JSON<textarea id="templateText" rows="12" spellcheck="false"></textarea></label><div class="actions"><button id="templatePreview">Ver cambios y conflictos</button><button id="templateApply" disabled>Aplicar al proyecto seleccionado</button></div><p>Los recursos idénticos se reutilizan. Un conflicto bloquea toda la importación. Después de aplicar, revisa el diff y prepara ambas herramientas.</p><pre id="templateResult" role="status" aria-live="polite"></pre></div>';
  main.appendChild(section);
  const button = document.createElement('button');
  button.dataset.page = 'templates';
  button.textContent = 'Plantillas';
  nav.appendChild(button);
  const el = (id) => document.getElementById(id),
    result = (text) => {
      el('templateResult').textContent = text;
    };
  const project = () => state.selected_project?.path || null;
  function invalidate() {
    preview = null;
    el('templateApply').disabled = true;
    el('templateDownload').disabled = !el('templateText').value;
  }
  function drafts() {
    return (
      window.hasUnsavedSkills?.() ||
      window.hasUnsavedAgents?.() ||
      (typeof agentEdits !== 'undefined' && agentEdits) ||
      (typeof workflowDirty !== 'undefined' && workflowDirty)
    );
  }
  button.onclick = () => {
    document.querySelectorAll('.nav button,.section').forEach((x) => x.classList.remove('active'));
    button.classList.add('active');
    section.classList.add('active');
    const title = el('title');
    if (title) title.textContent = 'Plantillas';
  };
  async function action(work) {
    if (busy) return;
    if (!project()) return result('Selecciona un proyecto.');
    if (drafts())
      return result(
        'Guarda o descarta los borradores de skills, agentes y workflows antes de continuar.',
      );
    busy = true;
    el('templateApply').disabled = true;
    try {
      await work();
    } catch (error) {
      invalidate();
      result(error.message);
    } finally {
      busy = false;
    }
  }
  el('templateText').addEventListener('input', invalidate);
  el('templateFile').onchange = async () => {
    const file = el('templateFile').files[0];
    if (!file) return;
    if (file.size > 1024 * 1024) return result('La plantilla supera 1 MiB.');
    if (el('templateText').value && !confirm('¿Reemplazar el contenido de plantilla abierto?'))
      return;
    el('templateText').value = await file.text();
    invalidate();
    result('Plantilla abierta; revisa y previsualiza antes de aplicar.');
  };
  el('templateExport').onclick = () =>
    action(async () => {
      if (
        el('templateText').value &&
        !confirm('¿Reemplazar el contenido de plantilla abierto con una nueva exportación?')
      )
        return;
      const selected = project(),
        text = el('templateText').value;
      const data = await api('/api/template/export', 'POST', {
        project_path: selected,
        name: el('templateName').value,
      });
      if (project() !== selected) throw new Error('El proyecto cambió durante la exportación.');
      if (el('templateText').value !== text)
        throw new Error('El contenido se editó durante la exportación; se conserva el borrador.');
      el('templateText').value = JSON.stringify(data.template, null, 2);
      invalidate();
      result('Exportación lista para revisar y descargar.');
    });
  el('templatePreview').onclick = () =>
    action(async () => {
      const text = el('templateText').value,
        selected = project();
      const template = JSON.parse(text);
      const data = await api('/api/template/preview', 'POST', { project_path: selected, template });
      if (project() !== selected || el('templateText').value !== text)
        throw new Error('El proyecto o la plantilla cambió; vuelve a previsualizar.');
      preview = { text, project: selected, token: data.token };
      result(JSON.stringify(data, null, 2));
      el('templateApply').disabled = !!data.conflicts.length;
    });
  el('templateApply').onclick = () =>
    action(async () => {
      const checked = preview;
      if (!checked || checked.project !== project() || checked.text !== el('templateText').value)
        throw new Error('Vuelve a previsualizar la plantilla en este proyecto.');
      if (!confirm('¿Aplicar los cambios revisados al proyecto seleccionado?')) {
        el('templateApply').disabled = false;
        return;
      }
      const data = await api('/api/template/apply', 'POST', {
        project_path: checked.project,
        template: JSON.parse(checked.text),
        token: checked.token,
        confirmed: true,
      });
      invalidate();
      result(JSON.stringify(data, null, 2));
      if (typeof refresh === 'function') await refresh();
    });
  el('templateDownload').onclick = () => {
    try {
      JSON.parse(el('templateText').value);
    } catch (error) {
      return result(error.message);
    }
    const url = URL.createObjectURL(
      new Blob([el('templateText').value], { type: 'application/json' }),
    );
    const link = document.createElement('a');
    link.href = url;
    link.download = 'factoria-template.json';
    link.click();
    URL.revokeObjectURL(url);
  };
})();

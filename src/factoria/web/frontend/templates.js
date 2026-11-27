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
  section.innerHTML = `
    <div class="grid">
      <div class="card full">
        <h2>Importar desde GitHub</h2>
        <p>Pega el enlace a un archivo público o abre una copia local. Revisa las instrucciones antes de añadirlas al proyecto. Factoría solo importa texto.</p>
        <div class="resource-basics">
          <label>Tipo de recurso<select id="sourceKind"><option value="skill">Skill</option><option value="agent">Agente</option></select></label>
          <label id="sourceRoleField" hidden>Función del agente<select id="sourceRole">
            <option value="explorer">Explorar</option><option value="planner">Planificar</option>
            <option value="implementer">Implementar</option><option value="reviewer">Revisar</option>
            <option value="documenter">Documentar</option>
          </select></label>
          <label>Identificador opcional<input id="sourceIdentifier" maxlength="64" placeholder="Se genera automáticamente"></label>
        </div>
        <div class="form-row">
          <label>Enlace al archivo<input id="sourceUrl" type="url" placeholder="https://github.com/…/blob/…/SKILL.md"></label>
          <button class="primary" id="sourceFetch">Descargar y revisar</button>
        </div>
        <div class="form-row">
          <label>Archivo local<input id="sourceFile" type="file" accept=".md,.toml"></label>
          <button class="secondary" id="sourceRead">Abrir y revisar</button>
        </div>
      </div>
      <div class="card full">
        <h2>Exportar recursos</h2>
        <p>Revisa el contenido antes de compartirlo.</p>
        <div class="resource-basics">
          <label>Nombre de plantilla<input id="templateName" maxlength="120" value="Mi plantilla"></label>
          <label>Qué exportar<select id="templateScope">
            <option value="">Proyecto completo</option><option value="skills">Skills</option>
            <option value="agents">Agentes y skills</option>
          </select></label>
        </div>
        <div class="actions"><button class="secondary" id="templateExport">Preparar exportación</button><button id="templateDownload" disabled>Descargar JSON</button></div>
      </div>
      <div class="card full" id="templateReview">
        <h2>Revisar plantilla</h2>
        <label>Abrir plantilla JSON<input id="templateFile" type="file" accept="application/json,.json"></label>
        <label>Contenido JSON<textarea id="templateText" rows="8" spellcheck="false"></textarea></label>
        <div class="actions"><button id="templatePreview">Ver cambios y conflictos</button><button class="primary" id="templateApply" disabled>Añadir al proyecto</button></div>
        <pre id="templateResult" role="status" aria-live="polite"></pre>
      </div>
    </div>`;
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
    return window.hasUnsavedProjectChanges();
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
  el('sourceKind').onchange = () => {
    el('sourceRoleField').hidden = el('sourceKind').value !== 'agent';
  };
  function openResource(remote) {
    return action(async () => {
      const selected = project();
      const text = el('templateText').value;
      if (text && !confirm('¿Reemplazar la plantilla abierta?')) return;
      const file = el('sourceFile').files?.[0];
      const url = el('sourceUrl').value.trim();
      if (remote && !url) throw new Error('Pega el enlace al archivo de GitHub.');
      if (!remote && !file) throw new Error('Selecciona un archivo Markdown o TOML.');
      if (!remote && file.size > 128 * 1024) throw new Error('El archivo supera 128 KiB.');
      const data = await api('/api/template/source', 'POST', {
        project_path: selected,
        kind: el('sourceKind').value,
        role: el('sourceRole').value,
        identifier: el('sourceIdentifier').value.trim(),
        ...(remote ? { url } : { filename: file.name, text: await file.text() }),
      });
      if (project() !== selected || el('templateText').value !== text || drafts())
        throw new Error('El proyecto o el borrador cambió. Vuelve a abrir el recurso.');
      el('templateText').value = JSON.stringify(data.template, null, 2);
      invalidate();
      const findings = await api('/api/template/preview', 'POST', {
        project_path: selected,
        template: data.template,
      });
      if (
        project() !== selected ||
        el('templateText').value !== JSON.stringify(data.template, null, 2) ||
        drafts()
      )
        throw new Error('El proyecto o el borrador cambió. Vuelve a previsualizar.');
      preview = { text: el('templateText').value, project: selected, token: findings.token };
      result(renderPreview(findings));
      el('templateApply').disabled = !!findings.conflicts.length;
      el('templateText').focus();
    });
  }
  function renderPreview(data) {
    return (
      [
        ...data.create.map((item) => 'Añadir: ' + item),
        ...data.reuse.map((item) => 'Ya existe: ' + item),
        ...data.conflicts.map((item) => 'Conflicto: ' + item),
      ].join('\n') || 'Sin cambios.'
    );
  }
  el('sourceFetch').onclick = () => openResource(true);
  el('sourceRead').onclick = () => openResource(false);
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
        scope: el('templateScope').value || null,
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
      result(renderPreview(data));
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
      result(
        'Importación completada. Prepara la integración para actualizar Codex y OpenCode.\n' +
          renderPreview(data),
      );
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

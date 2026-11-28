/* Render local memory with DOM text nodes so content never becomes executable HTML. */
function memoryViewerContent(open) {
  return `<details class="project-options memory-viewer" id="projectMemoryViewer" ${open ? 'open' : ''}>
    <summary>Consultar memoria</summary>
    <div class="memory-toolbar">
      <label>Buscar en los documentos<input type="search" maxlength="180" placeholder="Ej. reglas, arquitectura, pruebas"></label>
      <button type="button" class="secondary" data-memory-refresh>Actualizar memoria</button>
    </div>
    <p class="muted" role="status"></p>
    <ul class="memory-results" aria-label="Resultados de búsqueda" hidden></ul>
    <div class="memory-reading">
      <label>Documento<select></select></label>
      <article tabindex="-1" aria-label="Contenido del documento"></article>
    </div>
  </details>`;
}

function memorySections(markdown, title) {
  const sections = [{ title, level: 0, blocks: [] }];
  let fence = '',
    block = null,
    comment = false;
  for (const line of markdown.split(/\r?\n/)) {
    if (fence) {
      if (line.trim().startsWith(fence) && /^[`~]+$/.test(line.trim())) fence = '';
      else block.lines.push(line);
      continue;
    }
    if (comment || /^\s*<!--/.test(line)) {
      comment = !line.includes('-->');
      continue;
    }
    const marker = line.match(/^\s*(`{3,}|~{3,})/);
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    const item = line.match(/^\s*(?:([-*+])|(\d+)\.)\s+(.+)$/);
    if (heading) {
      sections.push({ title: heading[2], level: heading[1].length, blocks: [] });
      block = null;
      continue;
    }
    if (!line.trim()) {
      block = null;
      continue;
    }
    const type = marker ? 'pre' : item ? (item[2] ? 'ol' : 'ul') : 'p';
    if (!block || type !== block.type || marker) {
      block = { type, lines: [] };
      sections.at(-1).blocks.push(block);
    }
    if (marker) fence = marker[1];
    else block.lines.push(item ? item[3] : line.trim());
  }
  return sections;
}

function memoryText(element, text) {
  const pieces = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g);
  for (const piece of pieces) {
    const marker = piece.startsWith('`') ? '`' : piece.startsWith('**') ? '**' : '*';
    if (piece.length <= marker.length * 2 || !piece.startsWith(marker) || !piece.endsWith(marker)) {
      element.append(piece);
      continue;
    }
    const inline = document.createElement({ '`': 'code', '**': 'strong', '*': 'em' }[marker]);
    inline.textContent = piece.slice(marker.length, -marker.length);
    element.append(inline);
  }
}

function renderMemoryDocument(article, sections) {
  article.replaceChildren();
  for (const [index, section] of sections.entries()) {
    const node = document.createElement('section');
    node.dataset.memorySection = index;
    node.tabIndex = -1;
    if (section.level) {
      const heading = document.createElement('h' + Math.min(section.level + 2, 6));
      memoryText(heading, section.title);
      node.append(heading);
    }
    for (const { type, lines } of section.blocks) {
      const block = document.createElement(type);
      if (type === 'pre') block.textContent = lines.join('\n');
      else if (type === 'p') memoryText(block, lines.join(' '));
      else {
        for (const line of lines) {
          const item = document.createElement('li');
          memoryText(item, line);
          block.append(item);
        }
      }
      node.append(block);
    }
    article.append(node);
  }
}

function bindMemoryViewer(container, project) {
  const panel = container.querySelector('#projectMemoryViewer');
  const search = panel.querySelector('input');
  const select = panel.querySelector('select');
  const article = panel.querySelector('article');
  const results = panel.querySelector('ul');
  const status = panel.querySelector('[role="status"]');
  const refresh = panel.querySelector('[data-memory-refresh]');
  const reading = panel.querySelector('.memory-reading');
  let documents = [],
    loaded = false,
    pending = false;
  const normalize = (value) =>
    value.normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase('es');

  function showDocument(index) {
    select.value = index;
    renderMemoryDocument(article, documents[index].sections);
  }
  function showMatches() {
    const terms = normalize(search.value).trim().split(/\s+/).filter(Boolean);
    results.replaceChildren();
    results.hidden = !terms.length;
    if (!terms.length) return;
    for (const [index, doc] of documents.entries()) {
      for (const [sectionIndex, section] of doc.sections.entries()) {
        if (!terms.every((term) => section.search.includes(term))) continue;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'secondary';
        button.textContent =
          doc.title === section.title ? doc.title : doc.title + ' · ' + section.title;
        button.onclick = () => {
          showDocument(index);
          const target = article.querySelector(`[data-memory-section="${sectionIndex}"]`);
          target.focus();
          target.scrollIntoView({ block: 'nearest' });
        };
        const item = document.createElement('li');
        item.append(button);
        results.append(item);
        if (results.children.length >= 50) return;
      }
    }
    if (!results.children.length) {
      const item = document.createElement('li');
      item.textContent = 'No hay secciones que coincidan.';
      results.append(item);
    }
  }
  async function load() {
    if (pending) return;
    pending = true;
    refresh.disabled = search.disabled = true;
    reading.hidden = true;
    results.hidden = true;
    status.textContent = 'Leyendo la memoria…';
    try {
      const { documents: files, skipped } = await api('/api/project/memory-documents', 'POST', {
        project_path: project.path,
      });
      if (!panel.isConnected || state.selected_project?.path !== project.path) return;
      const current = documents[select.value]?.path;
      documents = files.map((doc) => {
        const sections = memorySections(doc.markdown, doc.title);
        for (const section of sections)
          section.search = normalize(
            [doc.title, section.title, ...section.blocks.flatMap((b) => b.lines)].join(' '),
          );
        return { ...doc, sections };
      });
      select.replaceChildren(...documents.map((doc, i) => new Option(doc.title, i)));
      reading.hidden = !documents.length;
      if (documents.length)
        showDocument(
          Math.max(
            0,
            documents.findIndex((doc) => doc.path === current),
          ),
        );
      status.textContent = [
        documents.length ? '' : 'Aún no hay documentos de memoria en este proyecto.',
        skipped.length ? 'No se pudieron mostrar: ' + skipped.join(', ') : '',
      ]
        .filter(Boolean)
        .join(' ');
      loaded = true;
      search.disabled = !documents.length;
      showMatches();
    } catch (error) {
      status.textContent = error.message;
    } finally {
      pending = refresh.disabled = false;
    }
  }
  reading.hidden = search.disabled = true;
  panel.ontoggle = () => {
    if (panel.open && !loaded) load();
  };
  refresh.onclick = load;
  search.oninput = showMatches;
  select.onchange = () => showDocument(Number(select.value));
  if (panel.open) load();
}

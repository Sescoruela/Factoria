/* Links define dependencies. Positions only affect the layout. */
let workflowDiagram = null;
let workflowDrag = null;
let workflowLinkSource = null;
let workflowScale = 1;

function workflowCanvas() {
  return document.getElementById('workflowCanvas');
}
function canvasStatus(message) {
  document.getElementById('workflowCanvasStatus').textContent = message;
}
function loadWorkflowDiagram(source) {
  workflowDiagram = structuredClone(source.diagram ?? null);
  workflowDraft = source.steps.map((step, i) => ({
    ...step,
    x: workflowDiagram?.nodes[step.name]?.x ?? canonicalX(i),
    y: workflowDiagram?.nodes[step.name]?.y ?? nodeY(i),
  }));
  workflowLinkSource = null;
  setWorkflowZoom(1);
  workflowCanvas().scrollTo(0, 0);
  canvasStatus(
    workflowDiagram && !workflowDiagram.execute
      ? 'Este diagrama aún es visual. Guarda una ruta válida para activarla.'
      : '',
  );
}
function clearWorkflowDiagram() {
  workflowDiagram = null;
  workflowDraft = [];
  workflowLinkSource = null;
  drawConnections();
  updateWorkflowLinks();
}
function workflowEdges() {
  if (workflowDiagram) return workflowDiagram.edges;
  const active = workflowDraft.filter((step) => step.enabled);
  return active.slice(1).map((step, index) => [active[index].name, step.name]);
}
function editableDiagram() {
  return (workflowDiagram ??= { nodes: {}, edges: workflowEdges() });
}
function workflowPorts(id, name = id) {
  return `<button type="button" class="port in" data-port="in" data-node="${id}" aria-label="Entrada de ${esc(name)}"></button><button type="button" class="port out" data-port="out" data-node="${id}" aria-label="Salida de ${esc(name)}" aria-pressed="false"></button>`;
}
function renderWorkflowDiagram() {
  const board = document.getElementById('workflowBoard');
  for (const [id, node] of Object.entries(workflowDiagram?.nodes ?? {})) {
    if (!Object.hasOwn(node, 'label')) continue;
    board.insertAdjacentHTML(
      'beforeend',
      `<div class="node diagram-note" style="left:${node.x}px;top:${node.y}px">
      ${workflowPorts(id, node.label)}<div class="node-header"><strong>${esc(node.label)}</strong></div>
      <div class="node-body"><button type="button" data-remove-note="${id}" aria-label="Eliminar caja ${esc(node.label)}">Eliminar caja</button></div></div>`,
    );
    board.lastElementChild.onpointerdown = (event) => startNodeDrag(event, id);
  }
  resizeWorkflowDiagram();
  drawConnections();
  updateWorkflowLinks();
}
function resizeWorkflowDiagram() {
  const inner = document.getElementById('canvasInner');
  const nodes = inner.querySelectorAll('.node');
  let width = 1500,
    height = 520;
  for (const node of nodes) {
    width = Math.max(width, node.offsetLeft + node.offsetWidth + 160);
    height = Math.max(height, node.offsetTop + node.offsetHeight + 160);
  }
  inner.style.width = width + 'px';
  inner.style.height = height + 'px';
}
const renderedWorkflowEdges = new Map();
function connectionPath(a, b) {
  const x1 = a.offsetLeft + a.offsetWidth,
    y1 = a.offsetTop + a.offsetHeight / 2;
  const x2 = b.offsetLeft,
    y2 = b.offsetTop + b.offsetHeight / 2;
  const bend = Math.max(60, Math.abs(x2 - x1) / 2);
  return `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`;
}
function drawConnections() {
  const svg = document.getElementById('connections');
  const nodes = new Map(
    [...document.querySelectorAll('#workflowBoard .port.out')].map((port) => [
      port.dataset.node,
      port.closest('.node'),
    ]),
  );
  svg.innerHTML =
    '<defs><marker id="workflowArrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto"><polygon fill="#7385ba" points="0,0 10,5 0,10"/></marker></defs>';
  renderedWorkflowEdges.clear();
  const paths = document.createDocumentFragment();
  for (const [from, to] of workflowEdges()) {
    const a = nodes.get(from),
      b = nodes.get(to);
    if (!a || !b) continue;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('marker-end', 'url(#workflowArrow)');
    path.setAttribute('d', connectionPath(a, b));
    paths.append(path);
    const edge = { a, b, path };
    for (const endpoint of [from, to]) {
      if (!renderedWorkflowEdges.has(endpoint)) renderedWorkflowEdges.set(endpoint, []);
      renderedWorkflowEdges.get(endpoint).push(edge);
    }
  }
  svg.append(paths);
}
function startNodeDrag(event, key) {
  if (event.button !== 0 || event.target.closest('select,input,label,button')) return;
  const stage = typeof key === 'number' ? workflowDraft[key] : null;
  const id = stage?.name ?? key;
  const node = stage ?? workflowDiagram.nodes[id];
  const card = event.currentTarget;
  workflowDrag = {
    id,
    node,
    stage,
    clientX: event.clientX,
    clientY: event.clientY,
    x: node.x,
    y: node.y,
  };
  card.setPointerCapture(event.pointerId);
  card.classList.add('dragging');
  card.onpointermove = moveWorkflowNode;
  card.onlostpointercapture = () => {
    card.classList.remove('dragging');
    card.onpointermove = null;
    workflowDrag = null;
    resizeWorkflowDiagram();
  };
}
function moveWorkflowNode(event) {
  if (!workflowDrag) return;
  const { id, node, stage, clientX, clientY, x, y } = workflowDrag;
  const limit = (value) => Math.min(50000, Math.max(0, Math.round(value)));
  const nextX = limit(x + (event.clientX - clientX) / workflowScale);
  const nextY = limit(y + (event.clientY - clientY) / workflowScale);
  if (nextX === node.x && nextY === node.y) return;
  Object.assign(node, { x: nextX, y: nextY });
  editableDiagram().nodes[id] = stage ? { x: nextX, y: nextY } : node;
  event.currentTarget.style.left = nextX + 'px';
  event.currentTarget.style.top = nextY + 'px';
  const inner = document.getElementById('canvasInner');
  inner.style.width =
    Math.max(inner.offsetWidth, nextX + event.currentTarget.offsetWidth + 160) + 'px';
  inner.style.height =
    Math.max(inner.offsetHeight, nextY + event.currentTarget.offsetHeight + 160) + 'px';
  for (const { a, b, path } of renderedWorkflowEdges.get(id) ?? [])
    path.setAttribute('d', connectionPath(a, b));
  markDirty();
}
function setWorkflowZoom(scale) {
  workflowScale = scale;
  document.getElementById('canvasInner').style.zoom = scale;
  document.getElementById('workflowZoom').textContent = Math.round(scale * 100) + ' %';
}
function zoomWorkflow(direction) {
  const canvas = workflowCanvas();
  const centerX = (canvas.scrollLeft + canvas.clientWidth / 2) / workflowScale;
  const centerY = (canvas.scrollTop + canvas.clientHeight / 2) / workflowScale;
  setWorkflowZoom(Math.max(0.01, Math.min(2, workflowScale * 1.25 ** direction)));
  canvas.scrollTo(
    centerX * workflowScale - canvas.clientWidth / 2,
    centerY * workflowScale - canvas.clientHeight / 2,
  );
}
function fitCanvas() {
  const canvas = workflowCanvas();
  const inner = document.getElementById('canvasInner');
  setWorkflowZoom(
    Math.min(1, canvas.clientWidth / inner.offsetWidth, canvas.clientHeight / inner.offsetHeight),
  );
  canvas.scrollTo(0, 0);
}
function addWorkflowNote() {
  if (!workflowRevision) return canvasStatus('Selecciona un workflow para añadir cajas.');
  const field = document.getElementById('workflowNoteName');
  const label = field.value.trim();
  if (!label) {
    field.focus();
    return canvasStatus('Escribe un nombre para la caja.');
  }
  const diagram = editableDiagram();
  if (
    Object.keys(diagram.nodes).length +
      workflowDraft.filter((step) => !diagram.nodes[step.name]).length >=
    1000
  )
    return canvasStatus('El diagrama admite hasta 1000 nodos.');
  const canvas = workflowCanvas();
  const x = Math.min(50000, Math.round((canvas.scrollLeft + 24) / workflowScale));
  const used = new Set(
    [...workflowDraft, ...Object.values(diagram.nodes)].map((node) => node.x + ',' + node.y),
  );
  let y = Math.min(50000, Math.round((canvas.scrollTop + 24) / workflowScale));
  while (used.has(x + ',' + y)) y = (y + 128) % 50001;
  diagram.nodes['note-' + crypto.randomUUID()] = { label, x, y };
  field.value = '';
  markDirty();
  renderWorkflowBoard();
  canvasStatus('Caja añadida.');
}
function updateWorkflowLinks() {
  for (const port of document.querySelectorAll('#workflowBoard .port.out'))
    port.setAttribute('aria-pressed', String(port.dataset.node === workflowLinkSource));
  const select = document.getElementById('workflowEdge');
  const selected = select.value;
  const label = (id) => workflowDiagram?.nodes[id]?.label ?? id;
  select.replaceChildren(
    ...workflowEdges().map(([from, to], i) => new Option(`${label(from)} → ${label(to)}`, i)),
  );
  if ([...select.options].some((option) => option.value === selected)) select.value = selected;
  document.getElementById('removeWorkflowEdge').disabled = select.options.length === 0;
}
function bypassWorkflowStage(id) {
  const edges = workflowDiagram.edges;
  const inputs = edges.filter(([, to]) => to === id).map(([from]) => from);
  const outputs = edges.filter(([from]) => from === id).map(([, to]) => to);
  const remaining = edges.filter((edge) => !edge.includes(id));
  if (
    inputs.length === 1 &&
    outputs.length === 1 &&
    inputs[0] !== outputs[0] &&
    !remaining.some(([from, to]) => from === inputs[0] && to === outputs[0])
  ) {
    remaining.push([inputs[0], outputs[0]]);
  }
  workflowDiagram.edges = remaining;
  if (workflowLinkSource === id) workflowLinkSource = null;
}
function removeWorkflowLink() {
  const value = document.getElementById('workflowEdge').value;
  if (value === '' || !workflowRevision) return;
  editableDiagram().edges.splice(Number(value), 1);
  markDirty();
  drawConnections();
  updateWorkflowLinks();
  canvasStatus('Conexión eliminada.');
}
document.getElementById('workflowBoard').addEventListener('click', (event) => {
  const port = event.target.closest('[data-port]');
  const remove = event.target.closest('[data-remove-note]');
  if (remove) {
    const id = remove.dataset.removeNote;
    delete workflowDiagram.nodes[id];
    workflowDiagram.edges = workflowDiagram.edges.filter((edge) => !edge.includes(id));
    if (workflowLinkSource === id) workflowLinkSource = null;
    markDirty();
    renderWorkflowBoard();
    canvasStatus('Caja eliminada.');
  }
  if (!port) return;
  const id = port.dataset.node;
  if (port.closest('.off')) return canvasStatus('Activa la etapa antes de conectarla.');
  if (port.dataset.port === 'out') {
    workflowLinkSource = workflowLinkSource === id ? null : id;
    updateWorkflowLinks();
    return canvasStatus(
      workflowLinkSource ? 'Elige la entrada de otra caja.' : 'Conexión cancelada.',
    );
  }
  if (!workflowLinkSource || workflowLinkSource === id)
    return canvasStatus('Elige primero la salida de otra caja.');
  const edges = workflowEdges();
  if (edges.some(([from, to]) => from === workflowLinkSource && to === id))
    return canvasStatus('Esas cajas ya están conectadas.');
  if (edges.length >= 4000) return canvasStatus('El diagrama admite hasta 4000 conexiones.');
  editableDiagram().edges.push([workflowLinkSource, id]);
  workflowLinkSource = null;
  markDirty();
  drawConnections();
  updateWorkflowLinks();
  canvasStatus('Conexión añadida.');
});

workflowCanvas().addEventListener('pointerdown', (event) => {
  if (event.button !== 0 || event.target.closest('.node') || event.target === workflowCanvas())
    return;
  const canvas = workflowCanvas();
  const { clientX, clientY } = event;
  const { scrollLeft, scrollTop } = canvas;
  canvas.setPointerCapture(event.pointerId);
  canvas.classList.add('panning');
  canvas.onpointermove = (move) => {
    canvas.scrollTo(scrollLeft + clientX - move.clientX, scrollTop + clientY - move.clientY);
  };
  canvas.onlostpointercapture = () => {
    canvas.classList.remove('panning');
    canvas.onpointermove = null;
  };
});

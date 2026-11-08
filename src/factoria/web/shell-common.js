const params = new URLSearchParams(location.search);
let token = params.get('token') || '';
try {
  token = token || sessionStorage.getItem('factoria-token') || '';
  if (token) sessionStorage.setItem('factoria-token', token);
} catch (e) {}
history.replaceState({}, document.title, location.pathname + location.hash);
const headers = { 'Content-Type': 'application/json', 'X-Factoria-Token': token };
let state = {};
async function api(path, method = 'GET', body) {
  const r = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || 'Error');
  return d;
}
function toast(m) {
  const t = document.getElementById('toast');
  t.textContent = m;
  t.style.display = 'block';
  setTimeout(() => (t.style.display = 'none'), 3200);
}
function esc(v) {
  return String(v ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  );
}

function renderPlatformCard(agent, defaultTool) {
  const isCodex = agent.name === 'codex';
  const cliAvailable = agent.cli_available ?? agent.available;
  const cli = `<div>CLI: <span class="pill ${cliAvailable ? 'warn' : 'bad'}">${cliAvailable ? 'DETECTADO · INICIO EXTERNO' : 'NO DETECTADO'}</span></div>`;
  const desktop = isCodex
    ? `<div>Codex en ChatGPT Desktop: <span class="pill warn">${agent.desktop_detected ? 'INDICIOS DE INSTALACIÓN DETECTADOS' : 'SIN INDICIOS LOCALES'}</span></div><p class="muted">Sesión y acceso al proyecto sin verificar. La detección de ChatGPT es independiente del CLI; puede incluir restos de una instalación. Si usas ChatGPT en el navegador, su disponibilidad no se puede deducir desde este equipo.</p>${agent.desktop_hint ? `<div class="muted">Indicio local: ${esc(agent.desktop_hint)}</div>` : ''}`
    : '';
  const source = agent.cli_source
    ? `<div class="muted">Origen del CLI: ${esc(agent.cli_source)}</div>`
    : '';
  const details = (agent.checks || [])
    .filter((check) => !check.passed && check.details)
    .map((check) => `<div class="muted">${esc(check.details)}</div>`)
    .join('');
  return `<div class="item"><strong>${esc(agent.name)}</strong>${defaultTool === agent.name ? '<span class="pill ok">PREDETERMINADO</span>' : ''}${desktop}${cli}${source}${details}<div class="actions"><button class="secondary" onclick="setDefaultAgent('${esc(agent.name)}')">Usar por defecto</button><button class="secondary" onclick="setAgentPath('${esc(agent.name)}')">Indicar ruta CLI</button></div></div>`;
}

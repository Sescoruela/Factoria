const params = new URLSearchParams(location.search);
let token = params.get('token') || '';
try {
  token = token || sessionStorage.getItem('factoria-token') || '';
  if (token) sessionStorage.setItem('factoria-token', token);
} catch (e) {}
history.replaceState({}, document.title, location.pathname);
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

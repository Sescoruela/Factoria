/* Deterministic renderer checks; real browser coverage lives in browser/. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assets = path.resolve(__dirname, '../../src/factoria/web');
for (const shell of ['shell-main.js', 'shell-classic.js']) {
  const card = {innerHTML: ''};
  const context = vm.createContext({
    URLSearchParams, location: {search: '', pathname: '/', hash: ''},
    sessionStorage: {getItem() { return ''; }}, history: {replaceState() {}},
    document: {title: 'fixture', getElementById() { return card; }},
  });
  vm.runInContext(fs.readFileSync(path.join(assets, 'shell-common.js'), 'utf8'), context);
  const source = fs.readFileSync(path.join(assets, shell), 'utf8');
  const start = source.indexOf('function renderAgents() {');
  vm.runInContext(source.slice(start, source.indexOf('\nfunction renderFlows()', start)), context);
  for (const desktop of [true, false]) {
    context.fixture = {name: 'codex', available: false, cli_available: false,
      desktop_detected: desktop, desktop_hint: '<unsafe>&', ready: false};
    vm.runInContext("state = {agents: [fixture], default_tool: 'codex'}; renderAgents();", context);
    assert.ok(card.innerHTML.includes(desktop ? 'INDICIOS DE INSTALACIÓN DETECTADOS' : 'SIN INDICIOS LOCALES'));
    assert.ok(card.innerHTML.includes('NO DETECTADO'));
    assert.ok(card.innerHTML.includes('Sesión y acceso al proyecto sin verificar'));
    assert.ok(card.innerHTML.includes('&lt;unsafe&gt;&amp;'));
    assert.ok(!card.innerHTML.includes('<unsafe>'));
  }
  context.fixture = {name: 'opencode', available: true};
  vm.runInContext('state = {agents: [fixture]}; renderAgents();', context);
  assert.ok(card.innerHTML.includes('DETECTADO · INICIO EXTERNO'));
  assert.ok(!card.innerHTML.includes('ChatGPT Desktop'));
}
console.log('Platform rendering: both shells passed (desktop, missing CLI, escaping, OpenCode).');

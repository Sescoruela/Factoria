/* Real Chromium + real local API. Only the failed-save response is injected. */
const {test: base, expect} = require('playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const token = 'disposable-browser-fixture';

const test = base.extend({
  lab: async ({request}, use) => {
    const response = await request.post('/__test__/reset', {headers: {'X-Factoria-Token': token}});
    expect(response.ok()).toBeTruthy();
    await use(await response.json());
  },
  page: async ({page}, use, info) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await use(page);
    await info.attach('page-errors', {body: JSON.stringify(errors), contentType: 'application/json'});
    expect(errors, 'Uncaught browser JavaScript errors').toEqual([]);
  },
});

const kinds = {
  skill: {nav: 'skills', field: '#skillContent', status: '#skillStatus',
    save: '#skillEditor button.primary', discard: '#skillEditor button.secondary',
    file: '.factoria/skills/browser-skill.md', endpoint: '/api/skill/save'},
  agent: {nav: 'agentRoles', field: '#agent-instructions', status: '#agentEditorStatus',
    save: '#saveAgentButton', discard: '#agentRoleEditor button.secondary',
    file: '.factoria/agents.json', endpoint: '/api/agent-role/save'},
  workflow: {nav: 'designer', field: '#workflowName', status: '#workflowDirty',
    save: '#designer button[onclick="saveWorkflow()"]',
    discard: '#designer button[onclick="resetWorkflowLocal()"]',
    file: '.factoria/workflows.json', endpoint: '/api/workflow/save'},
};

async function open(page, lab, shell, classicRoot = false) {
  const url = shell === 'main' ? lab.url : lab.classic_url;
  await page.goto(`${url}${shell === 'classic' && !classicRoot ? '/editors' : '/'}?token=${token}`);
  await expect(page).not.toHaveURL(/token=/);
  await expect(page.locator('#subtitle')).toContainText(lab.project);
  await expect(page.locator('#newWorkflowButton')).toBeEnabled();
}

async function nav(page, name) {
  await page.locator(`.nav [data-page="${name}"]`).click();
  await expect(page.locator(`#${name}`)).toHaveClass(/active/);
}

async function save(page, kind, expectedCode = 200) {
  const resource = kinds[kind];
  const response = page.waitForResponse(r => /\/api\/(skill|agent-role|workflow)\/(create|save)$/.test(new URL(r.url()).pathname) && r.request().method() === 'POST');
  await page.locator(resource.save).click();
  expect((await response).status()).toBe(expectedCode);
  if (expectedCode === 200) {
    if (kind === 'workflow') await expect(page.locator(resource.status)).toHaveText('');
    else await expect(page.locator(resource.status)).toContainText('Guardado.');
  } else await expect(page.locator(resource.status)).toContainText(/borrador.*conserv|Borrador conservado/);
  await expect(page.locator(resource.field)).toBeEnabled();
}

async function create(page, kind) {
  await nav(page, kinds[kind].nav);
  if (kind === 'skill') {
    await page.locator('#newSkillButton').click();
    await page.locator('#skillId').fill('browser-skill');
    await page.locator('#skillName').fill('Revisión de contratos');
    await page.locator('#skillDescription').fill('Reglas HTTP de prueba');
    await page.locator('#skillContent').fill('# Inicial\n\nConservar contratos.  \n');
  } else if (kind === 'agent') {
    await page.locator('#newAgentButton').click();
    await page.locator('#agent-id').fill('browser-reviewer');
    await page.locator('#agent-name').fill('Revisor de contratos');
    await page.locator('#agent-base').selectOption('reviewer');
    await page.locator('#agent-instructions').fill('Instrucciones iniciales');
  } else {
    await page.locator('#workflowTemplate').selectOption('feature');
    await page.locator('#newWorkflowButton').click();
    await page.locator('#workflowId').fill('browser-feature');
    await page.locator('#workflowName').fill('Workflow inicial');
  }
  await save(page, kind);
}

async function edit(page, kind) {
  await nav(page, kinds[kind].nav);
  if (kind === 'skill') await page.locator('#skillList .agent-editor').filter({hasText: 'browser-skill.md'}).getByRole('button', {name: 'Modificar'}).click();
  else if (kind === 'agent') await page.locator('#agentRoleList .agent-editor').filter({hasText: 'Revisor de contratos'}).getByRole('button', {name: 'Modificar'}).click();
  else {
    if (await page.locator('#workflowKind').inputValue() !== 'browser-feature') {
      await page.locator('#workflowKind').selectOption('browser-feature');
    }
    await expect(page.locator('#workflowId')).toHaveValue('browser-feature');
  }
  await expect(page.locator(kinds[kind].field)).toBeVisible();
}

function disk(lab, kind, project = 'project') {
  return fs.readFileSync(path.join(lab[project], kinds[kind].file), 'utf8');
}

async function discard(page, kind, accept) {
  const dialog = page.waitForEvent('dialog');
  const click = page.locator(kinds[kind].discard).click();
  const prompt = await dialog;
  expect(prompt.type()).toBe('confirm');
  await (accept ? prompt.accept() : prompt.dismiss());
  await click;
}

async function chooseProject(page, project) {
  await nav(page, 'projects');
  await page.locator('#projectList .item').filter({hasText: project}).getByRole('button', {name: 'Abrir', exact: true}).click();
}

for (const shell of ['main', 'classic']) {
  test.describe(shell, () => {
    test('create, edit, reload and reopen the linked three resource types', async ({page, lab}) => {
      await open(page, lab, shell);
      for (const kind of Object.keys(kinds)) await create(page, kind);
      await edit(page, 'agent');
      await page.locator('#agentSkillPicker').selectOption('.factoria/skills/browser-skill.md');
      await expect(page.locator('#agent-skills')).toHaveValue('.factoria/skills/browser-skill.md');
      await page.locator('#agent-instructions').fill('Revisar la compatibilidad HTTP');
      await save(page, 'agent');
      await edit(page, 'workflow');
      await page.locator('#workflowBoard .stage-agent').nth(3).selectOption('browser-reviewer');
      await page.locator('#workflowName').fill('Workflow final');
      await save(page, 'workflow');
      await edit(page, 'skill');
      const content = '# Revisión final\n\n- Conservar ñ y espacios.  \n';
      await page.locator('#skillContent').fill(content);
      await save(page, 'skill');
      expect(disk(lab, 'skill').endsWith(content)).toBeTruthy();
      expect(JSON.parse(disk(lab, 'agent'))['browser-reviewer'].skills).toEqual(['.factoria/skills/browser-skill.md']);
      expect(JSON.parse(disk(lab, 'workflow'))['browser-feature'].steps[3].agent_id).toBe('browser-reviewer');
      await page.reload();
      await expect(page.locator('#subtitle')).toContainText(lab.project);
      for (const [kind, value] of [['skill', content], ['agent', 'Revisar la compatibilidad HTTP'], ['workflow', 'Workflow final']]) {
        await edit(page, kind);
        await expect(page.locator(kinds[kind].field)).toHaveValue(value);
      }
      await expect(page.locator('#workflowBoard .stage-agent').nth(3)).toHaveValue('browser-reviewer');
    });

    for (const kind of Object.keys(kinds)) {
      test(`${kind}: refresh, cancelled navigation, failed save and retry retain draft`, async ({page, lab}) => {
        await open(page, lab, shell);
        await create(page, kind);
        const original = disk(lab, kind);
        await page.locator(kinds[kind].field).fill('Borrador pendiente');
        await page.getByRole('button', {name: 'Actualizar', exact: true}).click();
        await expect(page.locator(kinds[kind].field)).toHaveValue('Borrador pendiente');
        const prompt = page.waitForEvent('dialog');
        const attempt = chooseProject(page, lab.other);
        await (await prompt).dismiss();
        await attempt;
        await expect(page.locator('#subtitle')).toContainText(lab.project);
        await nav(page, kinds[kind].nav);
        await expect(page.locator(kinds[kind].field)).toHaveValue('Borrador pendiente');
        // Inject a transport-level save error; persistence still uses the real API on retry.
        await page.route('**' + kinds[kind].endpoint, route => route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({error: 'Fallo de guardado simulado'})}));
        await save(page, kind, 503);
        expect(disk(lab, kind)).toBe(original);
        await expect(page.locator(kinds[kind].field)).toHaveValue('Borrador pendiente');
        await page.unroute('**' + kinds[kind].endpoint);
        await save(page, kind);
        expect(disk(lab, kind)).toContain('Borrador pendiente');
      });

      test(`${kind}: real two-tab revision conflict and explicit discard`, async ({page, context, lab}, info) => {
        await open(page, lab, shell);
        await create(page, kind);
        const other = await context.newPage();
        const otherErrors = [];
        other.on('pageerror', error => otherErrors.push(error.message));
        await open(other, lab, shell);
        await edit(other, kind);
        await page.locator(kinds[kind].field).fill('Borrador de pestaña A');
        await other.locator(kinds[kind].field).fill('Guardado de pestaña B');
        await save(other, kind);
        const versionB = disk(lab, kind);
        await save(page, kind, 409);
        await expect(page.locator(kinds[kind].field)).toHaveValue('Borrador de pestaña A');
        expect(disk(lab, kind)).toBe(versionB);
        await discard(page, kind, false);
        await expect(page.locator(kinds[kind].field)).toHaveValue('Borrador de pestaña A');
        await discard(page, kind, true);
        if (kind !== 'workflow') await expect(page.locator(kinds[kind].field)).toHaveCount(0);
        await edit(page, kind);
        await expect(page.locator(kinds[kind].field)).toHaveValue('Guardado de pestaña B');
        await info.attach('second-tab-page-errors', {body: JSON.stringify(otherErrors), contentType: 'application/json'});
        expect(otherErrors).toEqual([]);
      });

      test(`${kind}: another tab changes project; stale save writes to neither project`, async ({page, context, lab}) => {
        await open(page, lab, shell);
        await create(page, kind);
        const original = disk(lab, kind);
        await page.locator(kinds[kind].field).fill('Borrador del proyecto original');
        const other = await context.newPage();
        await open(other, lab, shell);
        await chooseProject(other, lab.other);
        await expect(other.locator('#subtitle')).toContainText(lab.other);
        await page.getByRole('button', {name: 'Actualizar', exact: true}).click();
        await expect(page.locator('#subtitle')).toContainText(lab.other);
        await expect(page.locator(kinds[kind].field)).toHaveValue('Borrador del proyecto original');
        await page.locator(kinds[kind].save).click();
        // Either the saved origin reaches the server (409), or a periodic state
        // refresh has already detected the new project and blocks the request.
        const notice = kind === 'workflow' ? page.locator('#toast') : page.locator(kinds[kind].status);
        await expect(notice).toContainText(/proyecto/i);
        await expect(page.locator(kinds[kind].field)).toHaveValue('Borrador del proyecto original');
        expect(disk(lab, kind)).toBe(original);
        expect(fs.existsSync(path.join(lab.other, kinds[kind].file))).toBeFalsy();
        // A cancelled local discard must still preserve the old project's draft.
        await discard(page, kind, false);
        await expect(page.locator(kinds[kind].field)).toHaveValue('Borrador del proyecto original');
      });
    }
  });
}

test('classic root creates and reopens named workflow without the full-shell bridge', async ({page, lab}) => {
  await open(page, lab, 'classic', true);
  await create(page, 'workflow');
  await page.locator('#workflowName').fill('Clásico final');
  await save(page, 'workflow');
  await page.reload();
  await expect(page.locator('#subtitle')).toContainText(lab.project);
  await edit(page, 'workflow');
  await expect(page.locator('#workflowName')).toHaveValue('Clásico final');
});

test('API refuses unauthenticated writes on both servers', async ({request, lab}) => {
  for (const url of [lab.url, lab.classic_url]) {
    expect((await request.get(url + '/api/state')).status()).toBe(403);
    for (const resource of Object.values(kinds)) {
      expect((await request.post(url + resource.endpoint, {data: {project_path: lab.project}})).status()).toBe(403);
    }
  }
  expect(fs.existsSync(path.join(lab.project, '.factoria'))).toBeFalsy();
});

// Opt-in negative control for report/screenshot/trace plumbing, never a passing test.
if (process.env.FACTORIA_BROWSER_PROBE_FAILURE === '1') {
  test('intentional artifact probe', async ({page, lab}) => {
    await open(page, lab, 'main');
    expect('intentional failure for artifact inspection').toBe('PASS');
  });
}

/* Real Chromium + real local API. Only the failed-save response is injected. */
const {test: base, expect} = require('playwright/test');
const fs = require('node:fs');
const {execFileSync} = require('node:child_process');
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
  const button = page.locator(`.nav [data-page="${name}"]`);
  const menu = page.locator('#navToggle');
  if (await menu.isVisible() && await menu.getAttribute('aria-expanded') === 'false') {
    await menu.click();
  }
  const group = await button.evaluate(element => element.closest('.nav-links')?.id);
  if (group && !await button.isVisible()) {
    await page.locator(`button[aria-controls="${group}"]`).click();
  }
  await button.click();
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
    test('keeps form actions aligned and page layouts inside the viewport', async ({page, lab}) => {
      await open(page, lab, shell);
      const pages = await page.locator('.nav [data-page]').evaluateAll(buttons =>
        buttons.map(button => button.dataset.page));
      for (const width of [1440, 900, 390]) {
        await page.setViewportSize({width, height: 1000});
        for (const name of pages) {
          await nav(page, name);
          const hasOverflow = await page.evaluate(() =>
            document.documentElement.scrollWidth > document.documentElement.clientWidth);
          expect(hasOverflow, `${shell} / ${name} / ${width}px`).toBeFalsy();
        }
        for (const field of ['#workflowTemplate', '#projectsRootInput']) {
          await nav(page, field === '#workflowTemplate' ? 'designer' : 'projects');
          const row = page.locator('.form-row').filter({has: page.locator(field)});
          const input = await page.locator(field).boundingBox();
          const button = await row.getByRole('button').boundingBox();
          if (width > 560) {
            expect(Math.abs(input.y - button.y)).toBeLessThan(2);
            expect(Math.abs(input.height - button.height)).toBeLessThan(2);
          } else {
            expect(Math.abs(input.x - button.x)).toBeLessThan(2);
            expect(button.y).toBeGreaterThan(input.y + input.height);
          }
        }
      }
    });

    test('shows ChatGPT installation independently of a missing Codex CLI', async ({page, lab}) => {
      let desktopDetected = true;
      await page.route('**/api/state', async route => {
        const response = await route.fetch();
        const payload = await response.json();
        payload.agents = [{name: 'codex', available: false, cli_available: false,
          ready: false, desktop_detected: desktopDetected,
          desktop_hint: desktopDetected ? 'C:\\fixture\\OpenAI.ChatGPT-Desktop_<test>' : null}];
        await route.fulfill({response, json: payload});
      });
      await open(page, lab, shell, true);
      await nav(page, 'agents');
      const card = page.locator('#agentList');
      await expect(card).toContainText('INDICIOS DE INSTALACIÓN DETECTADOS');
      await expect(card).toContainText('CLI: NO DETECTADO');
      await expect(card).toContainText('Sesión y acceso al proyecto sin verificar');
      await expect(card).toContainText('OpenAI.ChatGPT-Desktop_<test>');
      await expect(card.locator('test')).toHaveCount(0);
      desktopDetected = false;
      await page.reload();
      await nav(page, 'agents');
      await expect(card).toContainText('SIN INDICIOS LOCALES');
      await expect(card).toContainText('CLI: NO DETECTADO');
    });
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

// H12 shared dirty-state contract: feature panels cannot replace an agent draft.
test('agent draft blocks relationship navigation in the canonical shell', async ({page, lab}) => {
  await open(page, lab, 'main');
  await create(page, 'agent');
  await page.locator('#agent-instructions').fill('Borrador que debe conservarse');
  await nav(page, 'relations');
  const target=page.locator('#relationsMap button').filter({hasText: 'feature'}).first();
  await expect(target).toBeEnabled();
  await target.click();
  await expect(page.locator('#relationsStatus')).toContainText('Se conservan los borradores');
  await nav(page, 'agentRoles');
  await expect(page.locator('#agent-instructions')).toHaveValue('Borrador que debe conservarse');
});

for(const shell of ['main','classic']) {
  test(`${shell}: migrate, checkpoint and restore from the recovery panel`, async ({page,lab})=>{
    await open(page,lab,shell);
    await create(page,'agent');
    const original=disk(lab,'agent');
    async function previewAndApply(){
      await page.locator('#configPreview').click();
      await expect(page.locator('#configStatus')).toContainText('Preview listo');
      const prompt=page.waitForEvent('dialog');
      const click=page.locator('#configApply').click();
      await (await prompt).accept();await click;
      await expect(page.locator('#configStatus')).toContainText('Operación completada');
    }
    await nav(page,'configuration');
    await expect(page.locator('#configStatus')).toContainText('Copias actualizadas');
    await previewAndApply();
    expect(JSON.parse(fs.readFileSync(path.join(lab.project,'.factoria/schema.json'),'utf8')).schema_version).toBe(1);
    await page.locator('#configAction').selectOption('snapshot');
    await previewAndApply();
    await page.locator('#configReload').click();
    const checkpoint=page.locator('#configBackup option').filter({hasText:'checkpoint'});
    await expect(checkpoint).toHaveCount(1);
    const identifier=await checkpoint.getAttribute('value');
    await edit(page,'agent');
    await page.locator('#agent-instructions').fill('Cambio después de la copia');
    await save(page,'agent');
    expect(disk(lab,'agent')).not.toBe(original);
    await nav(page,'configuration');
    await expect(page.locator('#configStatus')).toContainText('Copias actualizadas');
    await page.locator('#configAction').selectOption('restore');
    await page.locator('#configBackup').selectOption(identifier);
    await previewAndApply();
    expect(disk(lab,'agent')).toBe(original);
    await page.getByRole('button',{name:'Actualizar',exact:true}).click();
    await edit(page,'agent');
    await expect(page.locator('#agent-instructions')).toHaveValue('Instrucciones iniciales');
  });
}

// Presentation checks use real navigation and saved state, including the classic bridge.
test('overview lists actual resources and opens the selected workflow', async ({page,lab})=>{
  await open(page,lab,'main');
  await create(page,'skill');await create(page,'agent');await create(page,'workflow');
  await nav(page,'dashboard');
  await expect(page.locator('#title')).toHaveText('Inicio');
  await page.getByText('Configuración del proyecto', {exact: true}).click();
  await expect(page.locator('#dashboardGrid .workflow-row')).toHaveCount(3);
  await expect(page.locator('#dashboardGrid')).toContainText('1 skill');
  await page.locator('.workflow-row').filter({hasText:'Workflow inicial'}).click();
  await expect(page.locator('#designer')).toHaveClass(/active/);
  await expect(page.locator('#workflowKind')).toHaveValue('browser-feature');
  await expect(page.locator('.nav [data-page="designer"]')).toHaveAttribute('aria-current','page');
});

test('mobile menu supports keyboard navigation and projects fit the viewport', async ({page,lab})=>{
  await page.setViewportSize({width:390,height:844});
  await open(page,lab,'main');
  const menu=page.locator('#navToggle');
  await expect(menu).toHaveAttribute('aria-expanded','false');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link',{name:'Ir al contenido'})).toBeFocused();
  await menu.focus();await page.keyboard.press('Enter');
  await expect(menu).toHaveAttribute('aria-expanded','true');
  await page.getByRole('button', {name: 'Herramientas', exact: true}).focus();
  await page.keyboard.press('Escape');
  await expect(menu).toHaveAttribute('aria-expanded', 'false');
  await expect(menu).toBeFocused();
  await menu.click();
  await page.getByRole('navigation',{name:'Navegación principal'}).getByRole('button',{name:'Proyectos',exact:true}).click();
  await expect(page.locator('#projects')).toHaveClass(/active/);
  await expect(menu).toHaveAttribute('aria-expanded','false');
  await expect(page.locator('main')).toBeFocused();
  await expect(page.getByRole('textbox',{name:'Nombre del nuevo proyecto'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('mobile workflow editing keeps horizontal scrolling inside its canvas', async ({page,lab})=>{
  await page.setViewportSize({width:390,height:844});await open(page,lab,'main');
  await page.locator('#navToggle').click();await create(page,'workflow');
  await expect(page.locator('#workflowName')).toHaveValue('Workflow inicial');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  expect(await page.locator('#workflowCanvas').evaluate(el=>el.scrollWidth>el.clientWidth)).toBeTruthy();
});

test('empty workspace checks integration before choosing a project', async ({page,request,lab})=>{
  const response=await request.post(lab.url+'/__test__/reset',{headers:{'X-Factoria-Token':token},data:{selected:false}});
  const empty=await response.json();
  let opencodeDetected = false;
  await page.route('**/api/state', async route => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.agents = [
      {name: 'codex', cli_available: false, desktop_detected: true},
      {name: 'opencode', cli_available: opencodeDetected},
    ];
    await route.fulfill({response, json: payload});
  });
  const projectWrites = [];
  page.on('request', request => {
    if (['/api/project/prepare', '/api/command'].some(route => request.url().endsWith(route))) {
      projectWrites.push(request.url());
    }
  });
  await page.goto(empty.url+'/?token='+token);
  const startup = page.getByRole('article', {name: 'Revisar integración'});
  await expect(startup).toBeVisible();
  await expect(startup).toContainText('INDICIOS DE INSTALACIÓN DETECTADOS');
  const openCode = startup.locator('.item').filter({hasText: 'opencode'});
  await expect(openCode).toContainText('NO DETECTADO');
  opencodeDetected = true;
  await startup.getByRole('button', {name:'Volver a comprobar'}).click();
  await expect(openCode).toContainText('DETECTADO · INICIO EXTERNO');
  expect(projectWrites).toEqual([]);
  await expect(page.locator('#dashboardGrid .workflow-row')).toHaveCount(0);
  await startup.getByRole('button',{name:'Elegir proyecto',exact:true}).click();
  await page.locator('#projectList .item').filter({hasText:empty.project}).getByRole('button',{name:'Abrir',exact:true}).click();
  await expect(page.locator('#dashboard')).toHaveClass(/active/);
  await expect(page.getByRole('button', {name: 'Revisar preparación inicial'})).toBeVisible();
  await expect(startup).toHaveCount(0);
  await page.unrouteAll({behavior: 'wait'});
});

test('Inicio keeps prepared projects available for switching without listing other repositories', async ({page, request, lab}) => {
  const headers = {'X-Factoria-Token': token};
  const post = (route, data) => request.post(lab.url + route, {headers, data});
  const inactive = path.join(path.dirname(lab.project), 'inactive');
  execFileSync('git', ['init', '-b', 'main', inactive]);
  for (const project of [lab.project, lab.other]) {
    const selected = await post('/api/project/select', {path: project});
    expect(selected.ok()).toBeTruthy();
    const preview = await post('/api/project/prepare', {project_path: project});
    expect(preview.ok()).toBeTruthy();
    const {revision} = await preview.json();
    const prepared = await post('/api/project/prepare', {project_path: project, revision, confirmed: true});
    expect(prepared.ok()).toBeTruthy();
  }
  await open(page, {...lab, project: lab.other}, 'main');
  const projects = page.getByRole('region', {name: 'Proyectos con Factoría'});
  const first = projects.getByRole('button').filter({has: page.getByText(lab.project, {exact: true})});
  const second = projects.getByRole('button').filter({has: page.getByText(lab.other, {exact: true})});
  await expect(first).toBeVisible();
  await expect(second).toHaveAttribute('aria-current', 'true');
  await expect(projects.getByText(inactive, {exact: true})).toHaveCount(0);

  await first.click();
  await expect(page.locator('#dashboard')).toHaveClass(/active/);
  await expect(page.locator('#subtitle')).toContainText(lab.project);
  await expect(first).toHaveAttribute('aria-current', 'true');
  await expect(second).toBeVisible();
  await page.reload();
  await expect(first).toHaveAttribute('aria-current', 'true');
  await expect(second).toBeVisible();

  await projects.getByRole('button', {name: 'Gestionar proyectos'}).click();
  await expect(page.locator('#projectList').getByText(inactive, {exact: true})).toBeVisible();
});

test('classic overview opens the full skill editor in the same authenticated server', async ({page,lab})=>{
  await open(page,lab,'classic',true);
  await page.getByText('Configuración del proyecto', {exact: true}).click();
  await page.locator('#dashboardGrid [data-open-page="skills"]').click();
  await page.waitForURL('**/editors*');
  await expect(page.locator('#skills')).toHaveClass(/active/);
  await expect(page.locator('#subtitle')).toContainText(lab.project);
  await expect(page.locator('#newSkillButton')).toBeEnabled();
});

test('workflow connections meet the visible node ports after resizing the layout', async ({page,lab})=>{
  await open(page,lab,'main');await nav(page,'designer');
  await expect(page.locator('#workflowDetails')).not.toHaveAttribute('open','');
  const path=page.locator('#connections path').first();await expect(path).toBeAttached();
  const geometry=await page.locator('#canvasInner').evaluate(inner=>{
    const origin=inner.getBoundingClientRect();const source=inner.querySelector('.node .port.out').getBoundingClientRect();
    const target=inner.querySelectorAll('.node .port.in')[1].getBoundingClientRect();
    const numbers=inner.querySelector('#connections path').getAttribute('d').match(/-?\d+(?:\.\d+)?/g).map(Number);
    return {sourceY:source.y+source.height/2-origin.y,targetY:target.y+target.height/2-origin.y,lineSourceY:numbers[1],lineTargetY:numbers.at(-1)};
  });
  expect(Math.abs(geometry.sourceY-geometry.lineSourceY)).toBeLessThan(2);
  expect(Math.abs(geometry.targetY-geometry.lineTargetY)).toBeLessThan(2);
});


test('guided start reviews and prepares a fresh repository, copies a task and searches memory', async ({page, context, lab}) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await open(page, lab, 'main');
  const overview = page.locator('#dashboardGrid');
  await overview.getByRole('button', {name: 'Revisar preparación inicial'}).click();
  await expect(overview.getByText('Crea el primer commit', {exact: false})).toBeVisible();
  execFileSync('git', ['-C', lab.project, '-c', 'user.name=Factoría', '-c',
    'user.email=fixture@example.invalid', 'commit', '--allow-empty', '-m', 'Initial commit']);
  await overview.getByRole('button', {name: 'Revisar preparación inicial'}).click();
  await expect(overview.getByText('Tecnologías propuestas', {exact: false})).toBeVisible();
  const newFiles = [
    'AGENTS.md',
    '.factoria/integration-manifest.json',
    '.opencode/agents/factoria-explorer.md',
    '.opencode/commands/factoria-fix.md',
    '.agents/skills/factoria-fix/SKILL.md',
  ];
  await expect(overview.locator('.project-guide .guide-preview')).toContainText(newFiles[2]);
  await expect(overview.locator('.project-guide .guide-preview')).toContainText(newFiles[4]);
  for (const file of newFiles) expect(fs.existsSync(path.join(lab.project, file))).toBe(false);
  await overview.getByRole('button', {name: 'Preparar memoria, agentes y skills'}).click();
  await expect(overview.getByRole('button', {name: 'Añadir una funcionalidad'})).toBeVisible();
  for (const file of newFiles) expect(fs.existsSync(path.join(lab.project, file))).toBe(true);
  execFileSync('git', ['-C', lab.project, 'add', '-A']);
  expect(execFileSync('git', ['-C', lab.project, 'status', '--porcelain'], {encoding: 'utf8'})).toBe('');
  await overview.getByRole('button', {name: 'Añadir una funcionalidad'}).click();
  const description = overview.getByLabel('Describe la tarea');
  await description.fill('Añade turnos de 30 minutos');
  await expect(overview.getByLabel('Petición para pegar')).toHaveValue('$factoria-feature Añade turnos de 30 minutos');
  await overview.locator('#guidedTaskForm').getByLabel('Herramienta').selectOption('opencode');
  await overview.getByRole('button', {name: 'Copiar petición'}).click();
  await expect(overview.getByText('Petición copiada.')).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('/factoria-feature Añade turnos de 30 minutos');
  const navigation = page.getByRole('navigation', {name: 'Navegación principal'});
  await navigation.getByRole('button', {name: 'Configurar proyecto'}).click();
  await navigation.getByRole('button', {name: 'Memoria del proyecto'}).click();
  await expect(overview.locator('#projectMemoryGraph')).toHaveAttribute('open', '');
  await overview.getByRole('button', {name: 'Generar índice'}).click();
  await expect(overview.getByText(/Índice actualizado/)).toBeVisible();
  await overview.getByLabel('Qué buscar en la memoria').fill('Proyecto');
  await overview.getByRole('button', {name: 'Buscar en la memoria'}).click();
  await expect(overview.locator('#guideGraphResult')).toContainText('AGENTS.md');
});

test('imports a project memory review from an existing agent session', async ({page, context, lab}) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  fs.writeFileSync(path.join(lab.project, 'README.md'), '# Turnos');
  execFileSync('git', ['-C', lab.project, 'add', 'README.md']);
  execFileSync('git', ['-C', lab.project, '-c', 'user.name=Factoría', '-c',
    'user.email=fixture@example.invalid', 'commit', '-m', 'Document project']);
  const commit = execFileSync('git', ['-C', lab.project, 'rev-parse', 'HEAD'], {encoding: 'utf8'}).trim();
  await open(page, lab, 'main');
  const panel = page.locator('#projectMemoryReview');
  await panel.getByText('Analizar memoria con OpenCode o Codex').click();
  await panel.getByRole('button', {name: 'Copiar encargo de análisis'}).click();
  await expect(panel.getByText('Encargo copiado.')).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain('git rev-parse HEAD');
  await panel.getByLabel('Informe JSON').fill(JSON.stringify({
    commit,
    purpose: [{finding: 'Gestiona turnos de empleados.', sources: ['README.md']}],
    architecture: [], flows: [], contracts: [], decisions: [], checks: [],
    pending: ['Confirmar persistencia'],
  }));
  await panel.getByRole('button', {name: 'Revisar informe'}).click();
  await expect(panel.locator('pre')).toContainText('Gestiona turnos de empleados.');
  const target = path.join(lab.project, 'docs', 'memoria', 'revision.md');
  expect(fs.existsSync(target)).toBe(false);
  await panel.getByRole('button', {name: 'Guardar revisión'}).click();
  await expect(panel.getByText(/Revisión guardada/)).toBeVisible();
  expect(fs.readFileSync(target, 'utf8')).toContain('Confirmar persistencia');
  expect(execFileSync('git', ['-C', lab.project, 'status', '--porcelain'], {encoding: 'utf8'})).toBe('');
});

test('generates a memory proposal with the selected LLM and saves only after review', async ({page, lab}) => {
  fs.writeFileSync(path.join(lab.project, 'README.md'), '# Turnos');
  execFileSync('git', ['-C', lab.project, 'add', 'README.md']);
  execFileSync('git', ['-C', lab.project, '-c', 'user.name=Factoría', '-c',
    'user.email=fixture@example.invalid', 'commit', '-m', 'Document project']);
  const commit = execFileSync('git', ['-C', lab.project, 'rev-parse', 'HEAD'], {encoding: 'utf8'}).trim();
  await page.route('**/api/{state,command}', async route => {
    const response = await route.fetch();
    const payload = await response.json();
    (payload.state || payload).agents = [{name: 'opencode', cli_available: true}];
    await route.fulfill({response, json: payload});
  });
  const report = JSON.stringify({
    commit,
    purpose: [{finding: 'Gestiona turnos de empleados.', sources: ['README.md']}],
    architecture: [], flows: [], contracts: [], decisions: [], checks: [], pending: [],
  });
  await page.route('**/api/project/memory-review', async route => {
    const data = route.request().postDataJSON();
    if (data.action !== 'generate') return route.continue();
    expect(data.tool).toBe('opencode');
    const response = await route.fetch({postData: {...data, action: 'preview', report}});
    expect(response.status()).toBe(200);
    const proposal = await response.json();
    await route.fulfill({response, json: {...proposal, report, files_analyzed: 1}});
  });
  await open(page, lab, 'main');
  const overview = page.locator('#dashboardGrid');
  await overview.getByRole('button', {name: 'Revisar preparación inicial'}).click();
  await overview.getByRole('button', {name: 'Preparar memoria, agentes y skills'}).click();
  const panel = overview.locator('#projectMemoryReview');
  await panel.getByText('Analizar memoria con OpenCode o Codex').click();
  await panel.getByLabel('Herramienta para generar memoria').selectOption('opencode');
  await panel.getByRole('button', {name: 'Generar memoria', exact: true}).click();
  await expect(panel.locator('pre')).toContainText('Gestiona turnos de empleados.');
  const target = path.join(lab.project, 'docs', 'memoria', 'revision.md');
  expect(fs.existsSync(target)).toBe(false);
  await panel.getByRole('button', {name: 'Guardar revisión'}).click();
  await expect(panel.getByText(/Revisión guardada/)).toBeVisible();
  expect(fs.readFileSync(target, 'utf8')).toContain('README.md');
});

test('guided start identifies a conflicting file and preserves it', async ({page, lab}) => {
  const relative = '.agents/skills/factoria-fix/SKILL.md';
  const target = path.join(lab.project, relative);
  fs.mkdirSync(path.dirname(target), {recursive: true});
  fs.writeFileSync(target, '# Guía del proyecto\n');
  await open(page, lab, 'main');
  const guide = page.locator('.project-guide');
  await expect(guide.getByRole('heading', {name: 'Revisar qué impide continuar'})).toBeVisible();
  await expect(guide.getByText(relative, {exact: true})).toBeVisible();
  await expect(guide.getByRole('button', {name: 'Volver a comprobar'})).toBeVisible();
  expect(fs.readFileSync(target, 'utf8')).toBe('# Guía del proyecto\n');
});


test('navigation shows five main entries and opens the matching group for a direct link', async ({page, lab}) => {
  await open(page, lab, 'main');
  const menu = page.getByRole('navigation', {name: 'Navegación principal'});
  await expect(menu.locator(':scope > button, :scope > div > button')).toHaveText([
    'Inicio', 'Proyectos', 'Trabajo', 'Configurar proyecto', 'Herramientas',
  ]);
  await expect(menu.getByRole('button', {name: 'Ejecuciones', includeHidden: true})).toBeHidden();
  const work = menu.getByRole('button', {name: 'Trabajo', exact: true});
  await work.click();
  await menu.getByRole('button', {name: 'Ejecuciones', exact: true}).click();
  await expect(page.locator('#title')).toHaveText('Ejecuciones');
  await expect(work).toHaveAttribute('aria-expanded', 'true');

  await page.goto(lab.url + '/?token=' + token + '#page=configuration');
  const tools = menu.getByRole('button', {name: 'Herramientas', exact: true});
  await expect(tools).toHaveAttribute('aria-expanded', 'true');
  await expect(menu.getByRole('button', {name: 'Copias y recuperación'})).toHaveAttribute('aria-current', 'page');
  await expect(page.locator('#title')).toHaveText('Copias y recuperación');
});

test('the grouped classic menu opens the full project editors', async ({page, lab}) => {
  await open(page, lab, 'classic', true);
  const menu = page.getByRole('navigation', {name: 'Navegación principal'});
  await menu.getByRole('button', {name: 'Configurar proyecto', exact: true}).click();
  await menu.getByRole('button', {name: 'Preparar proyecto', exact: true}).click();
  await page.waitForURL('**/editors#page=integration');
  await expect(page.locator('#integration')).toHaveClass(/active/);
  await expect(menu.getByRole('button', {name: 'Configurar proyecto'})).toHaveAttribute('aria-expanded', 'true');
  await expect(menu.getByRole('button', {name: 'Preparar proyecto'})).toHaveAttribute('aria-current', 'page');
});

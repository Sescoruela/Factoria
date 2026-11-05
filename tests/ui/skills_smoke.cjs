/* Optional DOM/API smoke test. Requires jsdom as a development-only dependency. */
const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('fs'),assert=require('assert/strict');
const fixture=JSON.parse(process.env.FACTORIA_SKILL_FIXTURE);
let answer=false;const errors=[];
const pause=()=>new Promise(r=>setTimeout(r,20));
async function until(fn){for(let i=0;i<300;i++){if(fn())return;await pause();}throw Error('Timed out: '+fn);}
async function open(){
 const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
 const dom=await JSDOM.fromURL(fixture.url+'/?token=ui-test-token',{runScripts:'dangerously',resources:'usable',virtualConsole:vc,beforeParse(w){w.structuredClone=structuredClone;w.fetch=(url,opts)=>fetch(new URL(url,w.location.href),opts);w.confirm=()=>answer;}});
 await until(()=>typeof dom.window.saveSkill==='function'&&dom.window.eval('!!state.skill_catalog_revision'));
 return dom;
}
(async()=>{
 let dom=await open(),w=dom.window,d=w.document;
 function fill(id,value){const e=d.getElementById(id);assert.ok(e,id);e.value=value;e.dispatchEvent(new w.Event('input',{bubbles:true}));}
 const status=()=>d.getElementById('skillStatus').textContent;
 d.querySelector('.nav [data-page="skills"]').click();w.newSkill();
 fill('skillId','revision-api');fill('skillName','Revisión API');fill('skillDescription','Compatibilidad de contratos');
 const content='# Revisión\n\n- Mantener contratos.  \n';fill('skillContent',content);await w.saveSkill();assert.ok(status().startsWith('Guardado.'));
 const file=fixture.project+'/.factoria/skills/revision-api.md';assert.ok(fs.readFileSync(file,'utf8').endsWith(content));
 fill('skillContent','Borrador pendiente');await w.refresh();assert.equal(d.getElementById('skillContent').value,'Borrador pendiente');
 answer=false;await w.selectProject(fixture.other);assert.equal(w.eval('state.selected_project.path'),fixture.project);
 const changed=await w.api('/api/project/select','POST',{path:fixture.other});w.eval('state='+JSON.stringify(changed.state)+';renderAll()');
 assert.equal(d.getElementById('skillContent').value,'Borrador pendiente');await w.saveSkill();assert.ok(status().includes('proyecto de origen'));
 const restored=await w.api('/api/project/select','POST',{path:fixture.project});w.eval('state='+JSON.stringify(restored.state)+';renderAll()');
 fs.appendFileSync(file,'\nEdición externa');await w.saveSkill();assert.ok(status().includes('borrador se conserva'));assert.equal(d.getElementById('skillContent').value,'Borrador pendiente');
 assert.ok(fs.readFileSync(file,'utf8').endsWith('Edición externa'));
 answer=false;await w.discardSkill();assert.equal(d.getElementById('skillContent').value,'Borrador pendiente');
 answer=true;await w.discardSkill();w.editSkill('revision-api');assert.ok(d.getElementById('skillContent').value.endsWith('Edición externa'));
 const final='# Reglas finales\n\nConservar el contrato HTTP.\n';fill('skillContent',final);await w.saveSkill();assert.ok(status().startsWith('Guardado.'));
 w.newSkill();fill('skillId','revision-api');fill('skillName','Duplicada');fill('skillContent','No sobrescribir');await w.saveSkill();assert.ok(status().includes('Ya existe'));assert.ok(fs.readFileSync(file,'utf8').endsWith(final));
 answer=true;await w.discardSkill();
 d.querySelector('.nav [data-page="agentRoles"]').click();w.editAgentRole('reviewer');
 assert.equal(d.querySelectorAll('#agentSkillPicker option').length,2);
 w.assignCatalogSkill('.factoria/skills/revision-api.md');await w.saveAgentRole();
 assert.deepEqual(JSON.parse(fs.readFileSync(fixture.project+'/.factoria/agents.json')).reviewer.skills,['.factoria/skills/revision-api.md']);
 answer=true;await w.prepareIntegration(true);
 assert.ok(fs.readFileSync(fixture.project+'/.factoria/generated/skills.md','utf8').includes(final));
 assert.ok(fs.readFileSync(fixture.project+'/.agents/skills/factoria-fix/SKILL.md','utf8').includes('.factoria/skills/revision-api.md'));
 assert.ok(fs.readFileSync(fixture.project+'/.opencode/agents/factoria-reviewer.md','utf8').includes('.factoria/skills/revision-api.md'));
 assert.ok(w.eval('state.integration.ready'));
 dom.window.close();dom=await open();w=dom.window;d=w.document;
 d.querySelector('.nav [data-page="skills"]').click();w.editSkill('revision-api');assert.equal(d.getElementById('skillContent').value,final);
 fill('skillContent','Último cambio');await w.saveSkill();assert.equal(w.eval('state.integration.ready'),false);
 fill('skillContent','Pendiente al cerrar');const event=new w.Event('beforeunload',{cancelable:true});w.dispatchEvent(event);assert.ok(event.defaultPrevented);
 assert.deepEqual(errors,[]);dom.window.close();
 console.log('PASS: create/edit/reopen, refresh retention, external project/conflict, discard, duplicate, agent picker, both exports, stale integration and unload warning; no script errors.');
})().catch(e=>{console.error(e);process.exit(1);});

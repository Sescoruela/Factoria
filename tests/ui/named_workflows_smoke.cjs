/* Optional DOM/API smoke for named workflows in both shells. No LLM calls. */
const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('fs'),assert=require('assert/strict');
const fixture=JSON.parse(process.env.FACTORIA_SKILL_FIXTURE);
const errors=[];let answer=true;
const pause=()=>new Promise(r=>setTimeout(r,20));
async function until(fn){for(let i=0;i<300;i++){if(fn())return;await pause()}throw Error('Timed out: '+fn)}
async function open(url){
 const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
 const dom=await JSDOM.fromURL(url+'/?token=ui-test-token',{runScripts:'dangerously',resources:'usable',virtualConsole:vc,beforeParse(w){w.structuredClone=structuredClone;w.fetch=(url,opts)=>fetch(new URL(url,w.location.href),opts);w.confirm=()=>answer;}});
 await until(()=>dom.window.document.readyState==='complete'&&typeof dom.window.newWorkflow==='function'&&dom.window.eval('!!state.workflows?.feature?.revision'));
 return dom;
}
(async()=>{
 let dom=await open(fixture.url),w=dom.window,d=w.document;
 let current=await w.api('/api/state');
 await w.api('/api/agent-role/create','POST',{role:'api-reviewer',base_role:'reviewer',name:'API reviewer',profile:'rapido',instructions:'Check API contracts',skills:[],revision:current.agent_catalog_revision,project_path:fixture.project});
 dom.window.close();
 for(const [url,kind,id] of [[fixture.url,'feature','feature-api'],[fixture.legacy_url,'fix','fix-api']]){
  dom=await open(url);w=dom.window;d=w.document;
  const fill=(key,value)=>{const el=d.getElementById(key);el.value=value;el.dispatchEvent(new w.Event('input',{bubbles:true}));};
  d.querySelector('.nav [data-page="designer"]').click();
  d.getElementById('workflowTemplate').value=kind;
  const sourceSteps=JSON.stringify(w.eval('state.workflows')[kind].steps);
  w.newWorkflow();fill('workflowId',id);fill('workflowName','API '+kind);fill('workflowDescription','Compatibilidad HTTP');
  assert.equal(d.getElementById('workflowBase').value,kind);
  const select=d.querySelectorAll('#workflowBoard .stage-agent')[3];select.value='api-reviewer';select.dispatchEvent(new w.Event('change',{bubbles:true}));
  if(kind==='feature')assert.equal(d.querySelectorAll('#workflowBoard input[type="checkbox"]').length,0);
  await w.saveWorkflow();assert.equal(w.eval('workflowDirty'),false);assert.equal(d.getElementById('workflowKind').value,id);
  assert.equal(d.getElementById('workflowId').disabled,true);assert.equal(d.getElementById('workflowName').disabled,false);
  const file=fixture.project+'/.factoria/workflows.json';let saved=JSON.parse(fs.readFileSync(file));
  assert.equal(saved[id].kind,kind);assert.equal(saved[id].steps[3].agent_id,'api-reviewer');assert.equal(JSON.stringify(saved[kind].steps),sourceSteps);
  fill('workflowName','Nombre pendiente');await w.refresh();assert.equal(d.getElementById('workflowName').value,'Nombre pendiente');
  answer=false;d.getElementById('workflowKind').value=kind;await w.changeWorkflowKind();assert.equal(d.getElementById('workflowKind').value,id);
  await w.selectProject(fixture.other);assert.equal(w.eval('state.selected_project.path'),fixture.project);
  // Another editor changes the shared catalog; the metadata draft must survive the conflict.
  const live=await (await fetch(fixture.url+'/api/state',{headers:{'X-Factoria-Token':'ui-test-token'}})).json();
  const other = await fetch(fixture.url+'/api/agent-role/save',{method:'POST',headers:{'Content-Type':'application/json','X-Factoria-Token':'ui-test-token'},body:JSON.stringify({...live.agent_roles.find(a=>a.role==='api-reviewer'),instructions:'External catalog '+id,project_path:fixture.project,revision:live.agent_catalog_revision})});
  assert.equal(other.status,200);await w.saveWorkflow();assert.ok(d.getElementById('workflowDirty').textContent.includes('Borrador conservado'));
  assert.equal(d.getElementById('workflowName').value,'Nombre pendiente');assert.equal(JSON.parse(fs.readFileSync(file))[id].name,'API '+kind);
  answer=true;await w.resetWorkflowLocal();assert.equal(d.getElementById('workflowName').value,'API '+kind);
  fill('workflowName','Nombre final '+kind);await w.saveWorkflow();assert.equal(w.eval('workflowDirty'),false);
  d.getElementById('workflowTemplate').value=id;w.newWorkflow();fill('workflowId',id);fill('workflowName','Duplicado');await w.saveWorkflow();
  assert.ok(d.getElementById('workflowDirty').textContent.includes('Ya existe'));assert.equal(JSON.parse(fs.readFileSync(file))[id].name,'Nombre final '+kind);
  await w.resetWorkflowLocal();dom.window.close();
  dom=await open(url);w=dom.window;d=w.document;d.querySelector('.nav [data-page="designer"]').click();
  d.getElementById('workflowKind').value=id;await w.changeWorkflowKind();assert.equal(d.getElementById('workflowName').value,'Nombre final '+kind);
  assert.equal(d.querySelectorAll('#workflowBoard .stage-agent')[3].value,'api-reviewer');dom.window.close();
 }
 dom=await open(fixture.url);w=dom.window;await w.prepareIntegration(true);
 for(const id of ['fix-api','feature-api']){
  assert.ok(fs.readFileSync(fixture.project+`/.agents/skills/factoria-${id}/SKILL.md`,'utf8').includes('factoria native start '+id+' --tool'));
  assert.ok(fs.readFileSync(fixture.project+`/.opencode/commands/factoria-${id}.md`,'utf8').includes('agente `api-reviewer`'));
 }
 assert.ok(fs.readFileSync(fixture.project+'/.factoria/generated/workflows.md','utf8').includes('ambigua'));
 assert.deepEqual(errors,[]);dom.window.close();console.log('PASS both shells: named create/edit/reopen, compatible agents, fixed base controls, catalog preservation, draft/conflict/duplicate handling and both exports.');
})().catch(e=>{console.error(e);process.exit(1)});

/* Optional DOM/API smoke for H03. No LLM or provider process is started. */
const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('fs'),assert=require('assert/strict');
const fixture=JSON.parse(process.env.FACTORIA_SKILL_FIXTURE);
let answer=true;const errors=[];
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
 async function create(id,base_role){
  const state=await w.api('/api/state');
  const result=await w.api('/api/agent-role/create','POST',{role:id,name:id,base_role,profile:'rapido',platform:'opencode',instructions:'Custom instructions '+id,skills:[],project_path:fixture.project,revision:state.agent_catalog_revision});
  w.eval('state='+JSON.stringify(result.state)+';renderAll()');
 }
 await create('api-reviewer','reviewer');await create('api-writer','implementer');
 d.querySelector('.nav [data-page="designer"]').click();
 const reviewSelector=()=>d.querySelectorAll('#workflowBoard .stage-agent')[3];
 const options=()=>[...reviewSelector().options].map(x=>x.value);
 assert.ok(options().includes('api-reviewer'));assert.ok(!options().includes('api-writer'));
 reviewSelector().value='api-reviewer';reviewSelector().dispatchEvent(new w.Event('change',{bubbles:true}));
 assert.equal(w.eval('workflowDirty'),true);await w.saveWorkflow();assert.equal(w.eval('workflowDirty'),false);
 assert.equal(reviewSelector().value,'api-reviewer');assert.ok(!reviewSelector().textContent.includes('no disponible'));
 const file=fixture.project+'/.factoria/workflows.json';assert.equal(JSON.parse(fs.readFileSync(file)).feature.steps[3].agent_id,'api-reviewer');
 // A new catalog entry is available when revisiting a clean board.
 await create('second-reviewer','reviewer');d.querySelector('.nav [data-page="designer"]').click();assert.ok(options().includes('second-reviewer'));
 reviewSelector().value='second-reviewer';reviewSelector().dispatchEvent(new w.Event('change',{bubbles:true}));
 const snapshot=w.eval('JSON.stringify(workflowDraft)');const current=await w.api('/api/state');
 const agent=current.agent_roles.find(a=>a.role==='api-reviewer');
 await w.api('/api/agent-role/save','POST',{...agent,instructions:'External edit',project_path:fixture.project,revision:current.agent_catalog_revision});
 await w.saveWorkflow();assert.ok(d.getElementById('workflowDirty').textContent.includes('Borrador conservado'));assert.equal(w.eval('JSON.stringify(workflowDraft)'),snapshot);
 answer=false;await w.resetWorkflowLocal();assert.equal(w.eval('JSON.stringify(workflowDraft)'),snapshot);
 answer=true;await w.resetWorkflowLocal();assert.equal(reviewSelector().value,'api-reviewer');
 await w.prepareIntegration(true);assert.ok(fs.readFileSync(fixture.project+'/.agents/skills/factoria-feature/SKILL.md','utf8').includes('agente `api-reviewer`'));
 assert.ok(fs.readFileSync(fixture.project+'/.opencode/commands/factoria-feature.md','utf8').includes('External edit'));
 dom.window.close();
 // Legacy shell preserves and edits the same assignment, without the Python UI patch.
 dom=await open(fixture.legacy_url);w=dom.window;d=w.document;d.querySelector('.nav [data-page="designer"]').click();
 assert.equal(reviewSelector().value,'api-reviewer');assert.ok(!options().includes('api-writer'));
 reviewSelector().value='second-reviewer';reviewSelector().dispatchEvent(new w.Event('change',{bubbles:true}));await w.saveWorkflow();
 assert.equal(JSON.parse(fs.readFileSync(file)).feature.steps[3].agent_id,'second-reviewer');
 dom.window.close();
 dom=await open(fixture.url);w=dom.window;d=w.document;d.querySelector('.nav [data-page="designer"]').click();assert.equal(reviewSelector().value,'second-reviewer');
 assert.deepEqual(errors,[]);dom.window.close();
 console.log('PASS both shells: compatible agent selection, persist/reopen, catalog refresh, stale-agent conflict, draft retention and both tool guides.');
})().catch(e=>{console.error(e);process.exit(1)});

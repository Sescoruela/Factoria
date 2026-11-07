/* Real controller source, simulated DOM/API. No visual/browser claim. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
function harness({legacy=false,hash='',project='/project%name'}={}){
 const all=[],elements=new Map(),calls=[],edited=[],opened=[];
 function element(tag='div'){const item={tag,value:'',textContent:'',disabled:false,dataset:{},style:{},children:[],classList:{add(){},remove(){}},appendChild(child){this.children.push(child);},replaceChildren(){this.children=[];}};all.push(item);return item;}
 const nav=element(),main=element(),get=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
 const document={querySelector:s=>s==='.nav'?nav:s==='main.main'?main:null,querySelectorAll:()=>[],createElement:element,getElementById:get};
 const graph={project_path:project,revision:'r1',consistent:true,orphan_analysis_complete:true,integration:{status:'current'},diagnostics:[],nodes:[
  {key:'workflow:flow',kind:'workflow',id:'flow',label:'Flow',status:'active',enabled:true,editor:{kind:'workflow',id:'flow'}},
  {key:'stage:flow:implement',kind:'stage',label:'implement',role:'implementer',status:'active',profile:'potente',enabled:true,editor:{kind:'workflow',id:'flow'}},
  {key:'agent:custom',kind:'agent',id:'custom',label:'Agent <img src=x>',status:'active',editor:{kind:'agent',id:'custom'}},
  {key:'skill:rules',kind:'skill',id:'rules',label:'Rules',status:'active',editor:{kind:'skill',id:'rules'}}],edges:[
   {source:'workflow:flow',target:'stage:flow:implement',relation:'has_stage',enabled:true,valid:true},
   {source:'stage:flow:implement',target:'agent:custom',relation:'uses_agent',enabled:true,valid:true},
   {source:'agent:custom',target:'skill:rules',relation:'uses_skill',enabled:true,valid:true}]};
 let draft=false,defer=false,resolveGraph;const fresh={selected_project:{path:project},agent_roles:[{role:'custom'}],skills:[{id:'rules'}],workflows:{flow:{steps:[]}}};
 const context={document,window:{hasUnsavedSkills:()=>draft,open:(...args)=>opened.push(args),renderWorkflowList:id=>edited.push('list:'+id)},state:structuredClone(fresh),token:'fixture',location:{href:'http://localhost/',hash},URL,URLSearchParams,
  renderAll(){},loadWorkflowBoard:force=>edited.push('workflow:'+get('workflowKind').value+':'+force),
  api:async(route,method,payload)=>{calls.push({route,payload});if(route==='/api/state')return structuredClone(fresh);if(defer)return new Promise(resolve=>{resolveGraph=resolve;});return structuredClone(graph);}};
 if(!legacy){context.window.editAgentRole=id=>edited.push('agent:'+id);context.window.editSkill=id=>edited.push('skill:'+id);}
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../src/factoria/web/editor-state.js'),'utf8'),context);
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../src/factoria/web/relations.js'),'utf8'),context);
 const descendants=node=>[node,...node.children.flatMap(descendants)];
 return {context,get,graph,fresh,calls,edited,opened,all,
  button:label=>descendants(get('relationsMap')).find(e=>e.tag==='button'&&e.textContent.startsWith(label)),
  draft:value=>draft=value,defer:()=>defer=true,resolve:()=>{defer=false;resolveGraph(structuredClone(graph));}};
}
(async()=>{
 const h=harness();await h.get('relationsReload').onclick();
 assert.match(h.get('relationsStatus').textContent,/vigente/);
 await h.button('Flow').onclick();assert.ok(h.edited.includes('workflow:flow:true'));
 await h.button('Agent').onclick();assert.ok(h.edited.includes('agent:custom'));
 await h.button('Rules').onclick();assert.ok(h.edited.includes('skill:rules'));
 const count=h.edited.length;
 h.draft(true);await h.get('relationsReload').onclick();await h.button('Agent').onclick();assert.equal(h.edited.length,count);assert.match(h.get('relationsStatus').textContent,/borradores/);
 h.draft(false);h.defer();const navigation=h.button('Agent').onclick();h.draft(true);h.resolve();await navigation;
 assert.equal(h.edited.length,count);assert.match(h.get('relationsStatus').textContent,/borrador/);
 h.draft(false);h.graph.revision='r2';await h.button('Agent').onclick();assert.equal(h.edited.length,count);assert.match(h.get('relationsStatus').textContent,/cambiaron/);
 h.context.state.selected_project.path='/other';await h.button('Rules').onclick();assert.equal(h.edited.length,count);
 h.context.state.selected_project.path=h.graph.project_path;h.fresh.agent_configuration_error='bad';await h.button('Agent').onclick();assert.equal(h.edited.length,count);assert.match(h.get('relationsStatus').textContent,/no editable/);
 assert.ok(h.all.some(e=>e.tag==='button'&&e.textContent.includes('<img src=x>')));
 assert.ok(!h.all.some(e=>e.innerHTML&&e.innerHTML.includes('Agent <img')));
 const legacy=harness({legacy:true});await legacy.get('relationsReload').onclick();await legacy.button('Agent').onclick();
 const url=new URL(legacy.opened[0][0]);assert.equal(url.pathname,'/editors');assert.equal(url.searchParams.get('token'),'fixture');
 const target=JSON.parse(new URLSearchParams(url.hash.slice(1)).get('relation'));assert.equal(target.project,'/project%name');assert.equal(target.key,'agent:custom');
 const deep=harness({hash:url.hash});deep.context.renderAll();await new Promise(setImmediate);assert.ok(deep.edited.includes('agent:custom'));
 console.log('PASS relations controller: workflow/agent/skill editors, preserved drafts/races, stale source/project, literal labels, classic bridge and deep link (simulated DOM/API)');
})().catch(error=>{console.error(error);process.exitCode=1;});

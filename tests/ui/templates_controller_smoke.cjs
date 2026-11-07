/* Controller smoke with a minimal simulated DOM. Not a browser/visual test. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const elements = new Map();
function element() {
  return {value:'',textContent:'',disabled:false,events:{},dataset:{},classList:{add(){},remove(){}},
    appendChild(){},addEventListener(event,callback){this.events[event]=callback;},click(){}};
}
const nav=element(),main=element();
const document={querySelector:s=>s==='.nav'?nav:s==='main.main'?main:null,
  querySelectorAll:()=>[],createElement:element,
  getElementById:id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);}};
const calls=[];let pendingExport=null,conflict=false;
const context={document,window:{},state:{selected_project:{path:'/source'}},
  confirm:()=>true,api:async(route,method,payload)=>{
    calls.push({route,payload});
    if(route.endsWith('/export'))return new Promise(resolve=>{pendingExport=resolve;});
    if(route.endsWith('/preview'))return {token:'reviewed-revision',create:['agent:own'],reuse:[],conflicts:conflict?['agent:own']:[]};
    return {applied:true,project_path:payload.project_path};
  }};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../src/factoria/web/editor-state.js'),'utf8'),context);
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../src/factoria/web/templates.js'),'utf8'),context);
const get=id=>document.getElementById(id);
(async()=>{
  get('templateName').value='Equipo';
  const exporting=get('templateExport').onclick();
  get('templateText').value='new local draft';
  pendingExport({template:{name:'old response'}});await exporting;
  assert.equal(get('templateText').value,'new local draft');
  assert.match(get('templateResult').textContent,/borrador/);
  get('templateText').value='';
  const completed=get('templateExport').onclick();pendingExport({template:{name:'Equipo'}});await completed;
  context.state.selected_project.path='/target';
  await get('templatePreview').onclick();assert.equal(get('templateApply').disabled,false);
  context.state.selected_project.path='/another';
  await get('templateApply').onclick();
  assert.equal(calls.filter(c=>c.route.endsWith('/apply')).length,0);
  context.state.selected_project.path='/target';
  await get('templatePreview').onclick();
  get('templateText').value='{"name":"changed"}';get('templateText').events.input();
  assert.equal(get('templateApply').disabled,true);
  await get('templatePreview').onclick();await get('templateApply').onclick();
  const applied=calls.find(c=>c.route.endsWith('/apply'));
  assert.equal(applied.payload.project_path,'/target');assert.equal(applied.payload.confirmed,true);
  conflict=true;await get('templatePreview').onclick();assert.equal(get('templateApply').disabled,true);
  console.log('PASS template controller: export race, destination/content changes, apply and conflicts (simulated DOM)');
})().catch(error=>{console.error(error);process.exitCode=1;});

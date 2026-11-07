/* Controller test with simulated DOM/API; not a browser or visual check. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const elements=new Map();
function element(){return {value:'',textContent:'',disabled:false,events:{},dataset:{},style:{},children:[],classList:{add(){},remove(){}},
 addEventListener(event,callback){this.events[event]=callback;},replaceChildren(){this.children=[];this.value='';},
 appendChild(child){this.children.push(child);if(!this.value&&child.value)this.value=child.value;}};}
const nav=element(),main=element(),document={querySelector:s=>s==='.nav'?nav:s==='main.main'?main:null,querySelectorAll:()=>[],createElement:element,
 getElementById:id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);}};
let blocked=false,approve=true,defer=false,resolvePreview;const calls=[];
const context={document,window:{},state:{selected_project:{path:'/project'}},confirm:()=>approve,
 api:async(route,method,payload)=>{calls.push({route,payload});
  if(route.endsWith('/list'))return {active:[{kind:'skill',id:'rules',name:'Rules'}],history:[{kind:'skill',id:'old',status:'archived',archive_id:'a'.repeat(32)}]};
  if(route.endsWith('/preview')){if(defer)return new Promise(resolve=>{resolvePreview=resolve;});return {token:'revision',blockers:blocked?['agent:consumer']:[],snapshots_preserved:[]};}
  return {applied:true};}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../src/factoria/web/editor-state.js'),'utf8'),context);
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../src/factoria/web/resources.js'),'utf8'),context);
const get=id=>document.getElementById(id),applies=()=>calls.filter(c=>c.route.endsWith('/apply'));
(async()=>{
 get('resourceAction').value='duplicate';get('resourceNewId').value='copy';await get('resourceReload').onclick();
 await get('resourcePreview').onclick();assert.equal(get('resourceApply').disabled,false);
 get('resourceNewId').value='edited';get('resourceNewId').events.input();await get('resourceApply').onclick();assert.equal(applies().length,0);
 await get('resourcePreview').onclick();context.state.selected_project.path='/another';await get('resourceApply').onclick();assert.equal(applies().length,0);
 context.state.selected_project.path='/project';await get('resourceReload').onclick();
 await get('resourcePreview').onclick();approve=false;await get('resourceApply').onclick();assert.equal(applies().length,0);
 approve=true;await get('resourceApply').onclick();assert.equal(applies()[0].payload.request.new_id,'edited');assert.equal(applies()[0].payload.confirmed,true);
 blocked=true;get('resourceAction').value='archive';await get('resourceAction').onchange();await get('resourcePreview').onclick();assert.equal(get('resourceApply').disabled,true);
 blocked=false;get('resourceAction').value='restore';await get('resourceAction').onchange();await get('resourcePreview').onclick();await get('resourceApply').onclick();
 assert.equal(applies()[1].payload.request.archive_id,'a'.repeat(32));assert.equal(applies()[1].payload.request.action,'restore');
 get('resourceAction').value='duplicate';await get('resourceAction').onchange();get('resourceNewId').value='before';defer=true;
 const preview=get('resourcePreview').onclick();get('resourceNewId').value='after';resolvePreview({token:'old',blockers:[]});await preview;
 assert.equal(get('resourceApply').disabled,true);assert.match(get('resourceResult').textContent,/cambió/);
 console.log('PASS resource controller: stale draft/project, confirmation/cancel, references, restore and async preview (simulated DOM/API)');
})().catch(error=>{console.error(error);process.exitCode=1;});

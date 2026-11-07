/* Saved configuration map. Diagnostics never apply changes or start providers. */
(function(){
const nav=document.querySelector('.nav'),main=document.querySelector('main.main');if(!nav||!main)return;
let graph=null,busy=false,pending=null;
const section=document.createElement('section');section.id='relations';section.className='section';
section.innerHTML='<div class="card"><h2>Relaciones del proyecto</h2><p>Workflow → etapa → agente → skills. Configuración guardada: no incluye borradores ni snapshots de ejecuciones anteriores. Perfiles y plataformas son preferencias. Las verificaciones y aprobaciones obligatorias del tipo base siguen aplicándose, aunque no sean etapas configurables del mapa.</p><button id="relationsReload">Actualizar mapa</button><p id="relationsStatus" role="status" aria-live="polite"></p><div id="relationsMap" style="overflow:auto"></div><h3>Sin ruta activa desde un workflow permitido</h3><div id="relationsOrphans"></div><h3>Archivados o pendientes</h3><div id="relationsArchived"></div><h3>Diagnóstico</h3><pre id="relationsDiagnostics"></pre></div>';
main.appendChild(section);const navButton=document.createElement('button');navButton.dataset.page='relations';navButton.textContent='Relaciones';nav.appendChild(navButton);
const el=id=>document.getElementById(id),project=()=>state.selected_project?.path||null;
function drafts(){return (window.hasUnsavedSkills?.()||window.hasUnsavedAgents?.())||(typeof agentEdits!=='undefined'&&agentEdits)||(typeof agentSaving!=='undefined'&&agentSaving)||(typeof workflowDirty!=='undefined'&&workflowDirty)||(typeof workflowSaving!=='undefined'&&workflowSaving);}
function status(text){el('relationsStatus').textContent=text;}
function show(page,title){const target=el(page);if(!target)throw new Error('Editor no disponible');document.querySelectorAll('.nav button,.section').forEach(x=>x.classList.remove('active'));target.classList.add('active');document.querySelector(`.nav [data-page="${page}"]`)?.classList.add('active');if(el('title'))el('title').textContent=title;}
function text(tag,value){const element=document.createElement(tag);element.textContent=value;return element;}
function nodeButton(node){const button=document.createElement('button');button.className='secondary';button.textContent=`${node.label}${node.id&&node.id!==node.label?' ['+node.id+']':''} · ${node.status}${node.enabled===false?' · desactivada/bloqueada':''}`;button.disabled=!node.editor;button.onclick=()=>navigate(node.key);return button;}
function render(){
 const nodes=new Map(graph.nodes.map(n=>[n.key,n]));const map=el('relationsMap');map.replaceChildren();
 const table=document.createElement('table');table.style.width='100%';const head=document.createElement('tr');for(const title of ['Workflow','Etapa','Agente','Skills'])head.appendChild(text('th',title));table.appendChild(head);
 for(const workflow of graph.nodes.filter(n=>n.kind==='workflow'&&n.status==='active')){
  const stages=graph.edges.filter(e=>e.source===workflow.key&&e.relation==='has_stage').map(e=>nodes.get(e.target));
  for(const stage of stages){const row=document.createElement('tr');
   const flowCell=document.createElement('td');flowCell.appendChild(nodeButton(workflow));row.appendChild(flowCell);
   const stageCell=document.createElement('td');stageCell.appendChild(nodeButton(stage));stageCell.appendChild(text('div',`Rol ${stage.role} · ${stage.profile||'sin perfil'} · ${stage.tool||'sesión actual'}`));row.appendChild(stageCell);
   const edge=graph.edges.find(e=>e.source===stage.key&&e.relation==='uses_agent');const agent=nodes.get(edge?.target);
   const agentCell=document.createElement('td');if(agent)agentCell.appendChild(nodeButton(agent));if(edge&&!edge.valid)agentCell.appendChild(text('div','Referencia no disponible o rol incompatible'));row.appendChild(agentCell);
   const skillCell=document.createElement('td');if(agent)for(const link of graph.edges.filter(e=>e.source===agent.key&&e.relation==='uses_skill'))skillCell.appendChild(nodeButton(nodes.get(link.target)));row.appendChild(skillCell);table.appendChild(row);
  }
 }
 map.appendChild(table);
 for(const [id,items] of [['relationsOrphans',graph.nodes.filter(n=>n.orphan===true)],['relationsArchived',graph.nodes.filter(n=>['archived','pending'].includes(n.status))]]){
  const container=el(id);container.replaceChildren();for(const item of items)container.appendChild(nodeButton(item));
  if(!items.length){const unknown=id==='relationsOrphans'?!graph.orphan_analysis_complete:graph.diagnostics.some(d=>d.code==='invalid_archive'||(d.code==='source_unreadable_or_limit'&&d.subject.startsWith('.factoria/archive')));container.appendChild(text('p',unknown?'No evaluado: hay configuración incompleta.':'Sin elementos.'));}
 }
 const messages={unreachable_resource:'Sin ruta activa',invalid_catalog:'Catálogo JSON inválido',invalid_agent:'Agente no válido',invalid_skill:'Skill no válida',invalid_workflow:'Workflow no válido',invalid_archive:'Archivo de recursos no verificable',invalid_policy:'Política no válida',broken_skill_reference:'Skill no disponible',unsafe_skill_reference:'Ruta de skill no segura',broken_or_incompatible_agent_reference:'Agente no disponible o rol incompatible',reserved_resource_present:'Recurso activo con ID reservado',integration_unavailable:'No se puede comprobar la integración',source_unreadable_or_limit:'Fuente ilegible o superior al límite',source_changed_during_read:'El proyecto cambió durante la lectura'};
 el('relationsDiagnostics').textContent=graph.diagnostics.map(d=>`${d.severity==='error'?'Error':'Atención'} · ${messages[d.code]||d.code}: ${d.subject}`).join('\n')||'Sin incidencias.';
 if(graph.integration.status==='stale')el('relationsDiagnostics').textContent+=`\nIntegración pendiente de preparar. Cambios: ${(graph.integration.changed||[]).join(', ')}. Conflictos: ${(graph.integration.conflicts||[]).join(', ')}.`;
 const integration={current:'vigente',stale:'desactualizada',unavailable:'no verificable'}[graph.integration.status]||graph.integration.status;
 status(`Integración: ${integration}. ${graph.nodes.length} nodos, ${graph.edges.length} relaciones.${graph.consistent?'':' La lectura cambió: vuelve a actualizar.'}`);
}
async function reload(){const selected=project();if(!selected)throw new Error('Selecciona un proyecto');const data=await api('/api/project/relations','POST',{project_path:selected});if(project()!==selected)throw new Error('El proyecto cambió: vuelve a actualizar');graph=data;render();}
async function navigate(key){
 if(busy)return;busy=true;
 try{
  if(drafts())throw new Error('Se conservan los borradores. Guarda o descarta explícitamente antes de abrir otro editor.');
  if(!graph||!graph.consistent||project()!==graph.project_path)throw new Error('Actualiza el mapa de este proyecto');
  const selected=project(),revision=graph.revision;
  const current=await api('/api/project/relations','POST',{project_path:selected});
  if(project()!==selected||drafts())throw new Error('Cambió el proyecto o apareció un borrador; no se cambia el editor.');
  if(!current.consistent||current.revision!==revision){graph=current;render();throw new Error('Las relaciones cambiaron; revisa el mapa actualizado.');}
  const node=current.nodes.find(n=>n.key===key);if(!node?.editor)throw new Error('Recurso no editable desde el catálogo. Revisa su ruta o el archivo de recursos.');
  const editor=node.editor,fresh=await api('/api/state');
  if(project()!==selected||fresh.selected_project?.path!==selected||drafts())throw new Error('Cambió el proyecto o apareció un borrador; no se cambia el editor.');
  if((editor.kind==='agent'&&typeof window.editAgentRole!=='function')||(editor.kind==='skill'&&typeof window.editSkill!=='function')){
   const url=new URL('/editors',location.href);url.searchParams.set('token',token);url.hash='relation='+encodeURIComponent(JSON.stringify({project:selected,key}));
   window.open(url.href,'_blank','noopener');status('Se ha solicitado abrir el editor en otra pestaña. Si el navegador la bloquea, usa el enlace; esta vista se conserva.');
   const link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener';link.textContent=' Abrir editor';el('relationsStatus').appendChild(link);return;
  }
  if(editor.kind==='agent'&&(!fresh.agent_roles?.some(a=>a.role===editor.id)||fresh.agent_configuration_error))throw new Error('Catálogo de agentes no editable; corrige su diagnóstico primero.');
  if(editor.kind==='skill'&&(!fresh.skills?.some(s=>s.id===editor.id)||fresh.skill_configuration_error))throw new Error('Catálogo de skills no editable; corrige su diagnóstico primero.');
  if(editor.kind==='workflow'&&(!fresh.workflows?.[editor.id]||fresh.workflows[editor.id].error))throw new Error('Workflow no editable; corrige su diagnóstico primero.');
  state=fresh;renderAll();
  if(editor.kind==='workflow'){show('designer','Diseñador de flujo');window.renderWorkflowList?.(editor.id);el('workflowKind').value=editor.id;loadWorkflowBoard(true);}
  else if(editor.kind==='agent'){show('agentRoles','Agentes');window.editAgentRole(editor.id);}
  else {show('skills','Skills');window.editSkill(editor.id);}
 }catch(error){status(error.message);}finally{busy=false;}
}
navButton.onclick=()=>{show('relations','Relaciones');if(!busy){busy=true;reload().catch(e=>status(e.message)).finally(()=>busy=false);}};
el('relationsReload').onclick=async()=>{if(busy)return;busy=true;try{await reload();}catch(error){status(error.message);}finally{busy=false;}};
try{const value=new URLSearchParams(location.hash.slice(1)).get('relation');if(value)pending=JSON.parse(value);}catch(error){status('Enlace de editor no válido');}
const previousRender=renderAll;renderAll=function(){previousRender();if(pending&&state.selected_project){const target=pending;pending=null;if(target.project!==project())return status('El proyecto del enlace ya no está seleccionado.');reload().then(()=>navigate(target.key)).catch(error=>status(error.message));}};
})();

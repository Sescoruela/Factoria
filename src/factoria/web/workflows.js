/* Named workflow metadata; both shells share the same project-scoped API. */
(function(){
window.renderWorkflowList=function(preferred){
 if(workflowDirty&&preferred===undefined)return;
 const select=document.getElementById('workflowKind'),template=document.getElementById('workflowTemplate');
 const catalog=state.workflows||{};const chosen=preferred||select.value||'feature';const templateId=template.value||'feature';
 const options=Object.entries(catalog).map(([id,p])=>`<option value="${esc(id)}">${esc(p.name||id)} · ${esc(id)}</option>`).join('');
 select.innerHTML=options+(workflowCreating?'<option value="__new__">Nuevo workflow sin guardar</option>':'');
 select.value=workflowCreating?'__new__':(catalog[chosen]?chosen:(catalog.feature?'feature':Object.keys(catalog)[0]||''));
 template.innerHTML=options;template.value=catalog[templateId]?templateId:'feature';
 document.getElementById('newWorkflowButton').disabled=!state.selected_project||workflowSaving||!catalog[template.value]?.revision||!!catalog[template.value]?.error;
};
window.loadWorkflowMetadata=function(source){
 document.getElementById('workflowId').value=source.id||source.kind;document.getElementById('workflowId').disabled=true;
 document.getElementById('workflowName').value=source.name||source.kind;document.getElementById('workflowName').disabled=!source.id;
 document.getElementById('workflowDescription').value=source.description||'';document.getElementById('workflowDescription').disabled=!source.id;
 document.getElementById('workflowBase').value=source.kind;
};
window.workflowMetadataChanged=function(){if(workflowSaving)return;if(typeof markDirty==='function')markDirty();else markWorkflowDirty();};
window.newWorkflow=function(){
 if(!state.selected_project||!canLeaveWorkflow())return;
 const identifier=document.getElementById('workflowTemplate').value,source=state.workflows?.[identifier];
 if(!source?.revision||source.error)return toast('Recarga el catálogo antes de crear un workflow');
 workflowCreating=true;workflowOriginId=identifier;workflowProject=state.selected_project.path;workflowRevision=source.revision;
 workflowDraftKind=source.kind;workflowLoadedKind='__new__';
 workflowDraft=structuredClone(source.steps||[]).map((s,i)=>typeof canonicalX==='function'?{...s,x:canonicalX(i),y:nodeY(i)}:s);
 renderWorkflowList('__new__');
 document.getElementById('workflowId').value='';document.getElementById('workflowId').disabled=false;
 document.getElementById('workflowName').value='';document.getElementById('workflowName').disabled=false;
 document.getElementById('workflowDescription').value=source.description||'';document.getElementById('workflowDescription').disabled=false;
 document.getElementById('workflowBase').value=source.kind;
 workflowMetadataChanged();renderWorkflowBoard();document.getElementById('workflowId').focus();
};
renderWorkflowList();
if(!workflowDirty&&document.getElementById('designer').classList.contains('active'))loadWorkflowBoard(true);
})();

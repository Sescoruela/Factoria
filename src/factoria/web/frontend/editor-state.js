/* One conservative draft/saving guard for all auxiliary project panels. */
window.hasUnsavedProjectChanges = function () {
  return Boolean(
    window.hasUnsavedSkills?.() ||
      window.hasUnsavedAgents?.() ||
      (typeof agentEdits !== 'undefined' && agentEdits) ||
      (typeof agentSaving !== 'undefined' && agentSaving) ||
      (typeof workflowDirty !== 'undefined' && workflowDirty) ||
      (typeof workflowSaving !== 'undefined' && workflowSaving),
  );
};

// Keep generated identifiers editable until the user supplies their own.
function suggestResourceId(nameId, idId, prefix) {
  const name = document.getElementById(nameId);
  const id = document.getElementById(idId);
  let manual = Boolean(id.value);
  id.addEventListener('input', () => {
    manual = Boolean(id.value.trim());
  });
  name.addEventListener('input', () => {
    if (manual) return;
    const slug = name.value
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
    id.value = (slug && !/^[a-z]/.test(slug) ? prefix + '-' + slug : slug)
      .slice(0, 64)
      .replace(/-$/, '');
  });
}

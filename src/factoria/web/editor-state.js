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

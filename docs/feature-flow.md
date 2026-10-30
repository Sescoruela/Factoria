# Feature flow

The `feature` flow is stricter than `fix` and always requires explicit human gates.

## Lifecycle

1. Define the feature and acceptance criteria.
2. Build a plan.
3. Wait for plan approval.
4. Implement the approved plan.
5. Run required and optional verification.
6. Review against the original objective, acceptance criteria, and mandatory rules.
7. Update project memory when the change affects architecture, flows, decisions, or testing guidance.
8. Wait for final approval.
9. Complete the flow.

## Rules

- A feature cannot be planned without acceptance criteria.
- Implementation cannot start before plan approval.
- Any failed required verification blocks the flow.
- Critical or important review findings block closure.
- Mandatory-rule violations block closure.
- Memory updates are explicit before final approval when required.
- Final approval is always required for successful completion.

Functional and non-functional criteria are represented separately so reviewers can reason about both.

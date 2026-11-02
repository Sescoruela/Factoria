# MVP end-to-end validation

Factoria includes hermetic product-level tests that exercise the public CLI against temporary Git repositories rather than isolated application services.

## Covered journeys

The feature journey executes:

1. `factoria memoria-init` preview.
2. Explicit memory initialization with `--yes`.
3. A clean Git commit of the initialized project memory.
4. `factoria feature` on a dedicated branch.
5. Explorer and planner execution.
6. Explicit plan approval with `factoria resume --approve-plan`.
7. Implementer execution with controlled project-write permission.
8. Confirmed automated verification from project memory.
9. Structured reviewer approval.
10. Explicit final approval with `factoria resume --approve-final`.
11. Commit preview/creation through `factoria commit --yes`.
12. Archived execution history and final report inspection.
13. Operational `factoria status` after closure.

A second journey covers the small-fix path, which intentionally skips feature-style plan/final approval gates and reaches `ready_for_commit` only after implementation, verification and structured review.

## Agent fixture

CI does not depend on real provider credentials or remote model availability. It creates a temporary `opencode` executable that implements only the adapter contract required by the test:

- version and help probes;
- resolved-config safety probe;
- deterministic explorer/planner/implementer/reviewer/documenter behavior;
- deny-by-default permission checks;
- write permission only for the implementer;
- deterministic model routing evidence.

The fixture edits a real temporary repository, and Factoria then runs the repository's confirmed unit-test command through its normal verification path.

This validates Factoria's orchestration, lifecycle, Git, memory, review, verification, history and status integration. It does **not** claim that a particular external model/provider is available or reliable; real Codex/OpenCode installations remain covered by adapter self-tests and should also be exercised during local dogfooding.

## Regression found by the E2E

The first product-level run found a legacy CLI consumer still reading `phase` after runtime state had been unified around `runtime_stage`. Flow creation itself succeeded but the CLI crashed while rendering the persisted stage. The consumer now reads canonical `runtime_stage` (with legacy read fallback only), while persisted sessions continue to avoid writing a second `phase` state.

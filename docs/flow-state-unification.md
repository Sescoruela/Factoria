# Flow state unification

Factoria uses `FlowState` as the only lifecycle state machine.

Runtime progress is represented as structured metadata (`runtime_stage`) and must never duplicate lifecycle state semantics.

## Canonical lifecycle

- `created`
- `active`
- `paused`
- `blocked`
- `completed`
- `cancelled`

## Runtime stages

Live agent flows may persist a runtime stage such as:

- `running`
- `awaiting_plan_approval`
- `awaiting_final_approval`
- `ready_for_commit`

These values describe where the runtime is within a lifecycle state; they are not lifecycle states themselves.

`blocked` is never persisted as a runtime stage. Blocking is represented exclusively by `FlowState.BLOCKED`.

## Compatibility

Older workspaces may still contain an `agent-flow.json` field named `phase`. Factoria reads that field for compatibility and normalizes it into `runtime_stage`. A legacy `phase=blocked` does not become a second blocking state: the canonical state still comes from `state.toml`.

Contradictory persisted combinations are rejected rather than guessed.

## Invariants

- `active` requires `runtime_stage=running`.
- `paused` requires `awaiting_plan_approval`, `awaiting_final_approval`, or `ready_for_commit`.
- `blocked` has no resumable runtime stage.
- terminal states have no runtime stage.
- status, resume and commit validate the same invariants.

# Robust resume and cancel lifecycle

Factoria treats flow cancellation and Git branch deletion as separate operations.

## Resume

`factoria resume` without an ID lists interrupted flows and requires an explicit `flow_id` before continuing.

For live-agent flows Factoria checks the persisted flow branch before resuming:

- if the current branch differs, resume stops;
- `--switch-branch` explicitly authorizes switching to the flow branch, but only with a clean worktree;
- pending worktree changes are always reported;
- if a plan is still awaiting approval and the repository has changed, Factoria blocks resume instead of executing a potentially stale plan;
- final-review/commit phases may contain the implementation changes and keep their existing approval gates.

Example:

```bash
factoria resume
factoria resume <flow-id> --switch-branch
factoria resume <flow-id> --approve-plan
```

## Cancel

Cancellation previews the exact flow, associated branch, temporary workspace and temporary files before deleting anything.

```bash
factoria cancel <flow-id>
factoria cancel <flow-id> --yes
```

`--yes` cancels the flow and removes only Factoria's temporary workspace. It does **not** discard project changes and it does **not** delete the Git branch.

## Branch deletion is separate

To request deletion of the associated branch, both branch-deletion flags are required in addition to cancellation confirmation:

```bash
factoria cancel <flow-id> --yes --delete-branch --confirm-delete-branch
```

Factoria refuses to delete `main`.

If the flow branch contains commits that are not in `main`, Factoria lists their hashes and subjects and refuses deletion unless an explicit backup branch is created first:

```bash
factoria cancel <flow-id> --yes \
  --delete-branch --confirm-delete-branch \
  --backup-branch backup/<flow-id>
```

The backup branch is created before the original flow branch is removed.

Branch deletion also refuses to proceed while the worktree contains pending changes. Factoria never uses branch cleanup as an implicit way to discard local work.

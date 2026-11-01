# Manual verification gate

Factoria never treats the absence of automated checks as successful verification.

When `verification.md` contains confirmed automated checks, the existing automated result remains the verification evidence. When no confirmed automated check was selected, Factoria requires exact manual verification steps from project memory before the flow can be committed.

## Commit behavior

A normal preview remains available:

```bash
factoria commit <flow-id>
```

If manual verification is required, the preview prints the persisted steps. After completing every step, confirmation is explicit:

```bash
factoria commit <flow-id> --confirm-manual-verification --yes
```

The confirmation is written to `manual-verification.json` in the flow workspace before the commit. Because the execution history snapshots the workspace before terminal cleanup, this evidence survives cleanup in local history.

## Blocking cases

Closure is blocked when:

- `verification.md` is missing;
- no automated verification evidence exists and project memory has no manual verification steps;
- a commit is requested with `--yes` but required manual verification has not been explicitly confirmed.

The confirmation flag is not an assertion that Factoria executed the manual steps. It records the user's explicit confirmation that they were completed outside Factoria.

## Safety

Manual verification is a fallback, not a replacement for existing automated checks. Factoria continues to prefer confirmed automated project checks and does not create a testing framework as a side effect of a fix.

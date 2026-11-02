# Final reports and execution metrics

Factoria persists a stable final report for every terminal flow in the local Git history area (`git rev-parse --git-path factoria/history`). The report is local execution evidence and is not committed to the project repository.

## Final report

The report contains stable sections for:

- summary/objective and terminal state;
- branch and commit;
- persisted change summary when the flow was committed through Factoria;
- verification evidence;
- latest structured review evidence;
- sanitized security evidence, when such an artifact exists;
- permission profile and temporary escalation;
- agent attempts, fallbacks, adapters and concrete models actually recorded;
- usage metrics only when an adapter provides persisted evidence;
- a non-binding profile recommendation;
- the audited state-transition history and total duration.

Factoria never invents token or cost metrics. When the adapter did not expose them, the report says `usage_source: unavailable` and explicitly marks token/cost data as not estimated. Future adapters may persist `metrics_source=real` or `metrics_source=estimated` together with `input_tokens`, `output_tokens` and `cost_usd`; reports preserve that provenance.

Recommendations are informational only. Factoria never changes the execution/model profile automatically from historical metrics.

## Commit evidence

`factoria commit --yes` persists a local `commit.json` in the flow workspace before terminal archiving. It contains only:

- the created commit SHA;
- the confirmed commit message;
- the exact files included in the commit.

This makes the final report reproducible after the temporary workspace is removed.

## History

The compact history view now includes agent attempts, fallbacks, adapters and models when available:

```text
factoria history
```

A single execution can be selected:

```text
factoria history --flow-id <flow-id>
```

The full persisted report can be rendered with:

```text
factoria history --flow-id <flow-id> --report
```

`--report` requires `--flow-id` to avoid accidentally dumping many reports at once.

Retention remains bounded by the existing policy: at most 50 executions per project and at most 30 days, whichever removes a record first.

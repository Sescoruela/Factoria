# Structured review correction loop

Live `fix` and `feature` flows no longer treat a successful reviewer process exit as approval.

The reviewer must return a structured JSON result containing:

- `result`: `approved` or `changes_required`;
- `acceptance_criteria_met`: boolean;
- `mandatory_rules_violated`: array of strings;
- `findings`: severity (`critical`, `important`, `minor`), message and optional rule;
- `risks`: array of strings;
- `recommendation`: non-empty string.

Factoria validates the contract and rejects contradictory output. For example, `result=approved` is invalid when acceptance criteria are not met or a blocking finding exists.

## Closure rules

The review blocks closure when any of these conditions is true:

- a `critical` finding exists;
- an `important` finding exists;
- a mandatory project rule was violated;
- acceptance criteria are not fully met.

`minor` findings remain visible but do not block by themselves.

## Automatic correction

A blocking review starts an automatic correction cycle with the normal implementer role. The implementer receives only the blocking findings and is instructed not to expand scope.

After every correction Factoria:

1. executes the project's confirmed safe checks;
2. runs the reviewer again;
3. parses the new structured result.

At most two correction cycles are allowed. If blocking findings remain after the second correction, the flow is moved to `blocked` and requires manual inspection rather than looping indefinitely.

## Artifacts

The workspace keeps evidence for each cycle:

- `review.md`: latest raw reviewer output;
- `review.json`: latest normalized structured result;
- `review-cycle-N.md` / `review-cycle-N.json`: per-cycle evidence;
- `correction-N.txt`: implementer output for each correction cycle;
- `verification.md`: latest verification evidence.

These artifacts are included in the local execution-history snapshot when a terminal flow is archived.

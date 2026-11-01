# Operational status

`factoria status` is the lightweight operational dashboard for a project managed by Factoria.

It is designed to answer the questions that matter before starting or resuming work without repeating the full installation diagnosis on every invocation.

```bash
factoria status
factoria --project /path/to/repo status
factoria status --all
```

`--all` expands the recent execution section from five to ten archived results.

## What it shows

The command reports:

- current Git branch and whether the working tree has pending changes;
- project type (`active` / `maintenance`) when known;
- effective permission profile and configured coding-agent tool;
- project and organization blocked actions;
- allowed/blocked flows;
- project-memory review version, commits since review and stale documents;
- installed Codex/OpenCode presence and their declared Factoria capabilities;
- active/paused/blocked flows with their persisted phase and branch;
- recent execution results from the local Git-scoped history;
- potential secrets in currently modified files, using only redacted metadata/fingerprints;
- prioritized warnings and suggested next actions.

## Lightweight by design

`status` does **not** rerun adapter `--version` and `--help` self-tests. Those are intentionally kept in:

```bash
factoria install --check-only
```

This keeps normal status checks fast while still making unavailable configured tools visible.

## Memory version warnings

Project memory stores the Factoria version with which it was reviewed.

`status` warns when the installed version differs at MAJOR or MINOR level. PATCH-only differences do not generate a warning. This follows the project rule that patch releases should not create memory-version noise.

A version warning does not rewrite or migrate project memory. Use `factoria memoria-update` and review the proposal when a refresh is appropriate.

## Security signal

The security section scans only files currently reported as changed by Git. If a potential secret is found, the value itself is never printed. The status output contains only the secret category, path and a short fingerprint.

A finding is treated as a blocking operational warning. Remove the value and, when it was a real credential, rotate or revoke it outside Factoria before continuing.

## Deep diagnosis

Use `factoria install --check-only` when the status output reports an unavailable tool or when adapter capabilities need to be verified against the installed CLI. This separation keeps the common status path lightweight and the deeper environment diagnosis explicit.

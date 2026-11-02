# Adapter safety verification

Factoria separates a tool's declared CLI features from the safety capabilities that are verified before a live role may use the adapter.

## Safety capabilities

Two safety capabilities are explicit in the adapter contract:

- `read_only_enforcement`: required for explorer, planner, reviewer and documenter roles.
- `project_write_enforcement`: required for implementer/project-write roles.

An adapter that does not expose the capability required by a role is not a candidate for that stage, even if its ordinary CLI capabilities are otherwise compatible.

## Codex

Factoria permits Codex only for read-only roles in the built-in live policy. Its self-test probes the installed CLI parser with the exact restricted contract used by Factoria:

```text
--sandbox read-only --ask-for-approval never exec --help
```

The probe does not start an agent or modify a repository. A successful probe verifies that the installed Codex CLI accepts the restriction contract. It does **not** claim to empirically prove the implementation of the underlying OS sandbox; that enforcement remains provided by Codex itself.

Codex therefore declares `read_only_enforcement` but not `project_write_enforcement` in Factoria's built-in capability matrix.

## OpenCode

Factoria no relies on the undocumented `OPENCODE_PERMISSION` environment variable when launching OpenCode. The adapter translates Factoria's internal permission object into the documented `OPENCODE_CONFIG_CONTENT` inline runtime configuration.

The OpenCode self-test runs only:

```text
opencode debug config
```

inside a temporary directory. The temporary project deliberately contains permissive project configuration. Factoria supplies its restrictive inline runtime configuration and checks the resolved JSON. The probe succeeds only if the effective permission object still contains Factoria's required deny-by-default contract.

No model request or user-project command is executed by this probe.

The read-only contract denies everything by default and permits only read-oriented tools. The implementer contract also denies everything by default and permits `edit` in addition to read-oriented tools. Shell execution and external-directory access remain denied unless a future explicit, reviewed policy changes them.

## Failure behavior

Safety checks are required checks. If the installed tool version cannot verify the expected contract, setup reports the adapter as not ready and live orchestration will not select it for the affected role.

Factoria does not relax the requested permission profile, switch to a less restrictive safety contract, or treat a help-text match as proof of OpenCode's effective permissions.

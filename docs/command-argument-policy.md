# Adapter command argument policy

Factoria treats adapter CLI construction as a security boundary.

## Rule

`AgentRequest.extra_args` is retained for compatibility, but it is not free-form input. Every non-empty tuple must pass the selected adapter's `AdapterArgumentPolicy` before the adapter is allowed to build or execute a command.

Arguments are deny-by-default. A policy must explicitly declare each accepted flag and, for value-taking flags, every accepted value.

## Built-in adapters

### Codex

Factoria currently permits only the read-only safety pair used by read-only roles:

- `--sandbox read-only`
- `--ask-for-approval never`

Model selection, structured output, project location and bypass/elevation flags are controlled by Factoria and cannot be injected through `extra_args`.

### OpenCode

Factoria does not permit orchestration-supplied OpenCode CLI arguments. Project directory, output format and model are constructed directly by the adapter; role permissions are supplied through the approved `OPENCODE_PERMISSION` environment contract.

## External adapters

External Python plugins remain trusted code and are not sandboxed by Factoria. However, the orchestrator will not pass non-empty role arguments to an external adapter unless it exposes an explicit `argument_policy()` returning `AdapterArgumentPolicy`.

An adapter policy does not make arbitrary third-party Python safe; it only prevents Factoria's orchestration layer from handing undeclared CLI arguments to that adapter.

## Failure behavior

If a configured argument is not accepted, that adapter is rejected as an execution candidate. Factoria may select another verified compatible adapter, but it never relaxes the argument policy automatically.

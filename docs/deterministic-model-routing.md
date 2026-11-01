# Deterministic model routing

Factoria routes abstract model profiles (`rapido`, `equilibrado`, `potente`) to concrete models configured for each agent tool.

Live flows use strict routing. A requested profile must resolve to a concrete model for the selected adapter. Factoria does not silently fall back to the tool's implicit/default model when a mapping is missing.

Supported environment variables use the Factoria profile names:

- `FACTORIA_CODEX_RAPIDO`
- `FACTORIA_CODEX_EQUILIBRADO`
- `FACTORIA_CODEX_POTENTE`
- `FACTORIA_OPENCODE_RAPIDO`
- `FACTORIA_OPENCODE_EQUILIBRADO`
- `FACTORIA_OPENCODE_POTENTE`

The compatibility aliases (`MODEL_FAST`, `MODEL_BALANCED`, `MODEL_POWERFUL`) remain accepted by the live environment router, but the canonical profile variables take precedence.

## Runtime capability validation

An adapter is not selected only because its Python class declares a capability. The orchestrator performs the adapter self-tests and caches their result for the current process.

A candidate adapter must:

1. be installed and discoverable;
2. pass all required self-tests;
3. expose every capability required by the current role/stage;
4. satisfy the safety policy;
5. have a concrete model mapping when strict routing is enabled.

Required runtime capabilities include non-interactive execution and project-directory support. Structured stages additionally require structured output, and strict routing requires model selection.

If the preferred tool cannot satisfy the request, Factoria may use another configured compatible adapter, but it never relaxes the security policy or the model-profile requirement.

This makes failures explicit: a missing model mapping or incompatible installed CLI blocks the agent stage instead of changing behaviour silently.

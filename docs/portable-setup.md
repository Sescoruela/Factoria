# Portable setup and capability checks

Factoria now includes a first-run setup command:

```bash
factoria install
```

The command is deliberately preview-first. It inspects the local Python runtime, discovers the built-in Codex and OpenCode adapters, runs their adapter self-tests, compares their declared capabilities with the versioned capability matrix, and proposes a global configuration without writing it.

Use `--yes` only after reviewing the proposal:

```bash
factoria install --default-tool opencode --default-profile normal --yes
```

Use `--check-only` to rerun the environment diagnostics later without changing configuration:

```bash
factoria install --check-only
```

## Capability matrix

The built-in matrix lives in `src/factoria/adapters/capabilities.toml` and is packaged with Factoria. It records the capabilities expected from each built-in adapter. The runtime still asks the adapter for its declared capabilities, then the setup check verifies that the expected matrix is satisfied.

For the current built-ins the matrix tracks:

- non-interactive execution;
- structured output;
- model selection;
- project-directory support.

The self-tests also probe the actual installed CLI. Codex checks `codex --version` and `codex exec --help`; OpenCode checks `opencode --version` and `opencode run --help`. Missing required flags make the tool unavailable for automatic selection until the local installation is corrected or the adapter/matrix is updated.

## Global configuration safety

The setup command writes `~/.factoria/config.toml`. Files created by the wizard include the marker:

```text
# factoria: managed global config
```

Factoria may safely update a configuration containing that marker on later setup runs. If a pre-existing global config was created manually and does not contain the marker, the wizard shows the proposal but refuses to overwrite it automatically. This avoids silently dropping custom settings or comments.

No secrets, tokens, provider credentials, or machine-specific authentication values are written by the setup command.

## Python portability

The project currently declares Python `>=3.11`. `factoria install` reports the exact interpreter version it is running under and blocks automatic setup when that requirement is not met. This makes the remaining corporate-machine portability question visible instead of assuming compatibility.

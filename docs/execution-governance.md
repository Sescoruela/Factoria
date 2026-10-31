# Execution governance

Factoria applies execution restrictions in a fixed hierarchy:

1. organization hard policy
2. project policy
3. user preference
4. command/runtime override

A lower level may make execution more restrictive, but it must never relax a block imposed by a higher level.

## Policy sources

Organization hard restrictions are read from:

```text
~/.factoria/organization.toml
```

Example:

```toml
[permissions]
blocked_actions = ["destructive"]
```

Project restrictions live in the versioned project configuration:

```toml
[permissions]
blocked_actions = ["destructive"]
```

Supported action classes are `read`, `write`, `command`, and `destructive`.

The normal user preference comes from the global/project permission profile. A single command may request a temporary profile with the global CLI option:

```text
factoria --profile safe ...
factoria --profile normal ...
factoria --profile power ...
```

## Permission profiles

- `safe`: destructive actions are forbidden.
- `normal`: destructive actions require explicit confirmation.
- `power`: destructive actions may skip an additional confirmation only when the flow was already authorized.

A temporary switch to a more permissive profile is recorded in `permissions.json`, persisted with local execution history, and surfaced in the final execution report.

Some operations may impose a stronger product-level gate. For example, cancelling a flow still requires the explicit cancellation confirmation even under `power`.

Security gates such as secret detection remain blocking regardless of the selected permission profile.

# Execution governance

Factoria applies execution restrictions in a fixed hierarchy:

1. organization hard policy
2. project policy
3. user preference
4. command/runtime override

A lower level may make execution more restrictive, but it must never relax a block imposed by a higher level.

## Permission profiles

- `safe`: destructive actions are forbidden.
- `normal`: destructive actions require explicit confirmation.
- `power`: destructive actions may skip an additional confirmation only when the flow was already authorized.

Temporary escalation to a more permissive profile is recorded and must appear in the final execution report/history.

Security gates such as secret detection remain blocking regardless of the selected permission profile.

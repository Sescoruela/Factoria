# Secret detection and flow blocking

Factoria treats possible credentials, tokens, private keys and similar sensitive values as a hard security boundary.

## Rules

- Secret-like values are detected in changed files and in captured agent/check output.
- Detected values are never persisted or printed in full by Factoria.
- Any secret incident blocks the flow regardless of permission profile.
- A blocked incident may only be cleared after the user confirms the credential has been rotated/revoked outside Factoria and Factoria verifies the value no longer appears in the repository/workspace.
- Final reports record the incident in sanitized form and include preventive recommendations.
- Git commit preparation refuses to proceed while a secret incident is active.

## Detection

The initial implementation uses conservative high-confidence patterns for common credentials and private-key material plus assignment-style secret names. Findings contain only a type, source and sanitized fingerprint/preview; the raw value is kept in memory only long enough to verify removal.

This is a preventive layer, not a replacement for provider-side secret scanning or credential rotation procedures.

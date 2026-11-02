# Secret detection and persistent incidents

Factoria treats possible credentials, tokens, private keys and similar sensitive values as a hard security boundary.

## Rules

- Secret-like values are detected in changed files and in captured agent/check output.
- Detected values are never persisted or printed in full by Factoria.
- Any secret incident blocks the flow regardless of permission profile.
- Incidents are persisted locally under `.factoria/security/incidents.json`; that directory is ignored by Git.
- Persisted incident records contain only type, source, location, sanitized fingerprint, timestamps and lifecycle state.
- A blocked incident may only be resolved after the user confirms the credential has been rotated/revoked outside Factoria and Factoria verifies that the detected fingerprint no longer appears in the scope it can inspect.
- Git commit preparation refuses to proceed while any secret incident remains open.
- `factoria status` persists newly detected file incidents and reports open incidents even when the original scan happened in an earlier execution.

## Detection

The scanner uses conservative high-confidence patterns for common credentials and private-key material plus assignment-style secret names. Findings contain only a type, source and sanitized fingerprint/preview; raw values are kept in memory only while scanning and are never written to the incident store.

## Incident lifecycle

```text
detected -> open -> rotate/revoke externally -> confirm -> verify absent -> resolved
```

List incidents:

```bash
factoria security incidents
```

After rotating or revoking the credential outside Factoria and removing it from the repository/workspace, request resolution explicitly:

```bash
factoria security resolve <incident-id> --confirm-rotation
```

`--confirm-rotation` records the user's assertion that provider-side remediation has happened. It does not perform rotation or revocation. Factoria then scans the relevant file, or the locally inspectable changed/workspace files for output-origin incidents. If the same fingerprint is still detectable, the incident remains open and commit remains blocked.

Successful resolution records both the confirmation and resolution timestamps. Historical resolved incidents remain in the local incident store for auditability.

This is a preventive layer, not a replacement for provider-side secret scanning, credential revocation or organization incident-response procedures.

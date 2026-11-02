# Contract and external dependency impact

Factoria can persist confirmed contracts and cross-repository dependencies in project memory.

A contract declares the paths that implement or describe it, internal modules that consume it, and named external dependencies that may consume it. External dependencies store a stable name, repository reference and relationship description; they do not imply that the remote repository is currently broken or incompatible.

Impact analysis distinguishes evidence levels:

- `confirmed`: a changed path belongs to a declared module/contract, or a consumer was explicitly declared in memory.
- `inferred`: an internal module is reachable through the declared module impact graph.

Changing an internal module alone does not create an external blocking gate. A blocking external review is created only when a changed path matches a confirmed contract that explicitly names an external dependency.

Before commit, Factoria writes `impact.md` into the flow workspace. When external impact is confirmed, commit closure requires `--confirm-external-impact-review`. The confirmation is archived locally with the execution history. This flag means only that the user manually reviewed the declared consumer/contract impact; Factoria does not claim that another repository was tested unless separate evidence exists.

Example memory entries:

```text
## Contratos
- **public-api**: paths=backend/openapi.yaml; modules=frontend; external=mobile-app

## Dependencias externas
- **mobile-app**: repository=org/mobile-app; relationship=consumes REST API
```

These declarations are project memory and must be reviewed like other Factoria memory. Secrets, credentials and machine-specific values must not be stored in them.

# Factoria update and rollback

Factoria uses Semantic Versioning for released versions. The update flow is deliberately explicit: it checks a Git clone, previews the target version and changes, and never updates without confirmation.

## Check for updates

```bash
factoria update
```

By default Factoria looks for the Git checkout that contains the installed source. If it cannot find one, provide it explicitly:

```bash
factoria update --source /path/to/Factoria
```

The default source is `origin/main`; both can be changed with `--remote` and `--branch`.

The preview shows the installed version, target version, target commit, up to 20 new commits, and release notes when `src/factoria/release.toml` is present in the target commit.

No update is applied until the same command is repeated with `--yes`.

```bash
factoria update --yes
```

## How an update is applied

Factoria fetches the target commit for inspection but does not reset, rewrite, or check out the development clone. After confirmation it installs the exact target commit using the active Python interpreter and `pip`.

Before installation it stores one rollback record under:

```text
~/.factoria/update-state/previous.json
```

That record contains the previous version/commit, the target version/commit, the Git remote URL and, when applicable, the contents of the Factoria-managed global configuration. It never stores provider credentials or model secrets.

A health check is executed after installation. A failed health check does not trigger an automatic rollback; the user decides whether to roll back.

## Rollback

Rollback is always manual and requires confirmation:

```bash
factoria rollback --yes
```

It reinstalls the previous exact commit, restores the previously generated `~/.factoria/config.toml` when Factoria managed that file, and runs the health check again. A successful rollback clears the one-step rollback record. A failed rollback keeps it for diagnosis.

## MAJOR releases

Every version requires confirmation. For a MAJOR upgrade Factoria additionally shows memory/configuration compatibility notes from `release.toml` when provided.

Project memory is never migrated automatically in this first update implementation. The user remains in control of any memory or configuration migration.

## Release metadata

A release may include:

```toml
version = "1.0.0"
notes = ["General release note"]
memory_changes = ["Review architecture memory format"]
config_changes = ["Review renamed setting"]
```

The `version` must match the target `pyproject.toml` version or the update is blocked.

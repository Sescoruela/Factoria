# Factoria update and rollback

Factoria uses Semantic Versioning for released versions. The update flow is deliberately explicit: it checks a Git clone, previews the target version and changes, and never updates without confirmation.

## Exact installation provenance

Safe rollback depends on knowing the exact Git commit that produced the currently installed package. Factoria therefore keeps installation provenance under:

```text
~/.factoria/update-state/installed.json
```

The record contains the installed semantic version, exact commit SHA, source Git remote and installation timestamp. If that file does not exist, Factoria may recover the same evidence from Python's `direct_url.json` metadata when the package was installed from a pinned Git commit.

Factoria does **not** use the current `HEAD` of a source clone as a substitute for installation provenance. A clone may have moved since installation and is not evidence of what is actually installed.

Before an update can be applied Factoria verifies that:

- the provenance version matches the installed package version;
- the provenance remote matches the configured update remote;
- the recorded commit exists in the source checkout after fetch;
- the installed commit is an ancestor of the selected remote target.

If exact provenance is unavailable, update application is blocked rather than creating an unsafe rollback record.

## Check for updates

```bash
factoria update
```

By default Factoria looks for the Git checkout that contains the installed source. If it cannot find one, provide it explicitly:

```bash
factoria update --source /path/to/Factoria
```

The default source is `origin/main`; both can be changed with `--remote` and `--branch`.

The preview shows the installed version, target version, target commit, verified installed commit when available, up to 20 commits between those exact revisions, and release notes when `src/factoria/release.toml` is present in the target commit.

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

That record contains the **previous installed commit from verified provenance**, the target version/commit, the Git remote URL and, when applicable, the contents of the Factoria-managed global configuration. It never stores provider credentials or model secrets.

After installation, `installed.json` is updated to the exact target commit. The health check then imports the updater and CLI parser and confirms that Python package metadata reports the expected semantic version. A failed health check does not trigger an automatic rollback; the user decides whether to roll back.

## Rollback

Rollback is always manual and requires confirmation:

```bash
factoria rollback --yes
```

Before reinstalling anything, Factoria checks that the currently installed provenance still matches the update target recorded in `previous.json`. If another installation has replaced it in the meantime, rollback is refused rather than guessing.

A valid rollback reinstalls the exact previous commit, restores the previously generated `~/.factoria/config.toml` when Factoria managed that file, updates `installed.json` back to the previous revision, and runs the health check again. A successful rollback clears the one-step rollback record. A failed rollback keeps it for diagnosis.

## MAJOR releases

Every version requires confirmation. For a MAJOR upgrade Factoria additionally shows memory/configuration compatibility notes from `release.toml` when provided.

Project memory is never migrated automatically in this update implementation. The user remains in control of any memory or configuration migration.

## Release metadata

A release may include:

```toml
version = "1.0.0"
notes = ["General release note"]
memory_changes = ["Review architecture memory format"]
config_changes = ["Review renamed setting"]
```

The `version` must match the target `pyproject.toml` version or the update is blocked.

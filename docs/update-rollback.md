# Factoria update and rollback

Factoria uses Semantic Versioning for released versions. Stable updates are deliberately explicit: Factoria previews an immutable tagged release, verifies its source identity, and never installs it without confirmation.

## Exact installation provenance

Safe rollback depends on knowing the exact Git commit that produced the currently installed package. Factoria therefore keeps installation provenance under:

```text
~/.factoria/update-state/installed.json
```

The record contains the installed semantic version, exact commit SHA, source Git remote and installation timestamp. Tagged installations additionally record the release tag and Git tree SHA. If that file does not exist, Factoria may recover commit provenance from Python's `direct_url.json` metadata when the package was installed from a pinned Git commit.

Factoria does **not** use the current `HEAD` of a source clone as a substitute for installation provenance. A clone may have moved since installation and is not evidence of what is actually installed.

Before an update can be applied Factoria verifies that:

- the provenance version matches the installed package version;
- the provenance remote matches the configured update remote;
- the recorded commit exists in the source checkout after fetch;
- a recorded tree SHA still matches the recorded commit;
- the installed commit is an ancestor of the selected release.

If exact provenance is unavailable, update application is blocked rather than creating an unsafe rollback record.

## Immutable release selection

The configured branch remains a **release channel**, not the installation target. By default this is `origin/main`.

Factoria queries remote tags named `v<semver>`, selects the newest release newer than the installed version, and verifies that its commit is reachable from the configured channel. The branch itself is never installed.

Example tags:

```text
v0.3.0
v0.4.0
v1.0.0
```

To inspect a particular release:

```bash
factoria update --tag v0.4.0
```

The `v` prefix may be omitted on the CLI, but release tags in Git use the `vX.Y.Z` format.

Annotated and lightweight tags are both resolved to their final commit. For annotated tags, Factoria uses the peeled commit rather than the tag-object SHA.

## Check for updates

```bash
factoria update
```

By default Factoria looks for the Git checkout that contains the installed source. If it cannot find one, provide it explicitly:

```bash
factoria update --source /path/to/Factoria
```

`--remote` changes the trusted Git remote and `--branch` changes the release channel. A selected release tag must be reachable from that channel.

The preview shows:

- installed version;
- selected release tag;
- target semantic version;
- exact target commit SHA;
- target Git tree SHA;
- verified release channel;
- exact installed commit when provenance is available;
- up to 20 commits between the installed and target revisions;
- release notes from `src/factoria/release.toml` when present.

No update is applied until the same command is repeated with `--yes`.

```bash
factoria update --yes
```

## Integrity checks before installation

Previewing a release is not enough. Immediately before installation Factoria resolves the remote tag again.

The update is aborted if:

- the tag no longer points to the commit that was reviewed;
- the source tree SHA no longer matches the reviewed commit;
- the tag version does not match `project.version` in `pyproject.toml`;
- `release.toml`, when present, declares a different version;
- the tag commit is not reachable from the configured release channel.

This prevents a moved/replaced tag from silently changing the code between preview and confirmation. Factoria then installs by **full commit SHA**, not by mutable tag or branch name.

Git commit and tree identifiers provide content-addressed source identity. This milestone does not claim cryptographic signer identity: signed-tag/signature policy is a separate future hardening layer.

## How an update is applied

Factoria fetches objects for inspection but does not reset, rewrite, or check out the development clone. After confirmation it installs the exact reviewed commit using the active Python interpreter and `pip`.

Before installation it stores one rollback record under:

```text
~/.factoria/update-state/previous.json
```

That record contains the **previous installed commit from verified provenance**, the target version/commit/tag/tree, the Git remote URL and, when applicable, the contents of the Factoria-managed global configuration. It never stores provider credentials or model secrets.

After installation, `installed.json` is updated to the exact target release evidence. The health check then imports the updater and CLI parser and confirms that Python package metadata reports the expected semantic version. A failed health check does not trigger an automatic rollback; the user decides whether to roll back.

## Rollback

Rollback is always manual and requires confirmation:

```bash
factoria rollback --yes
```

Before reinstalling anything, Factoria checks that the currently installed provenance still matches the update target recorded in `previous.json`, including recorded tree integrity when available. If another installation has replaced it in the meantime, rollback is refused rather than guessing.

A valid rollback reinstalls the exact previous commit, restores the previously generated `~/.factoria/config.toml` when Factoria managed that file, restores the previous provenance record, and runs the health check again. A successful rollback clears the one-step rollback record. A failed rollback keeps it for diagnosis.

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

The `version` must match both the selected `vX.Y.Z` tag and target `pyproject.toml` version or the update is blocked.

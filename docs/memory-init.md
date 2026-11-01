# Complete `memoria-init`

`factoria memoria-init` is the first-time bootstrap for a repository. It is intentionally proposal-first: repository evidence is inspected, a complete memory/configuration proposal is printed, and nothing is persisted until the user confirms it with `--yes`.

## What is proposed

The bootstrap proposes:

- project type (`active` or `maintenance`) from the last 30 days of Git activity;
- detected technologies;
- path-based modules;
- module dependencies when there is concrete repository evidence;
- existing verification commands;
- non-functional priorities;
- `.factoria/config.toml` with the memory type and per-document staleness thresholds;
- the normal Factoria memory files (`AGENTS.md` and detailed documents appropriate to the project type).

The activity classification is a heuristic. Override it before confirmation when necessary:

```bash
factoria memoria-init --kind maintenance
```

## Evidence and confirmation

Detected values remain proposals until `--yes` is supplied. The preview prints the evidence used for commands and dependencies. Current conservative evidence sources are:

- scripts already declared in `package.json` (`build`, `test`, `lint`, `typecheck`, `smoke`);
- `.sln`/`.csproj` files for .NET build/test proposals;
- an existing Python `tests/` suite, with pytest used only when pytest configuration is declared;
- package dependencies between detected modules;
- `.NET` `ProjectReference` entries;
- Python imports that directly reference another detected top-level module.

Factoria does not create a testing framework merely because none is present.

After review:

```bash
factoria memoria-init --purpose "..." --yes
```

At that point the proposed values become confirmed project memory.

## Project configuration

The initial configuration is deliberately small and contains no machine-specific tool choice:

```toml
# factoria: managed project config

[flows]
allowed = []
blocked = []

[permissions]
blocked_actions = []

[memory]
type = "active"

[memory.staleness]
architecture = 25
flows = 25
decisions = 25
testing = 25
```

The default staleness threshold is 25 commits per document and can be changed later per project.

If `.factoria/config.toml` already exists, `memoria-init` preserves it and warns instead of overwriting it.

## Non-functional priorities

Priorities are context for planning/review, not automatic policy changes. The initial conservative proposal is:

- maintainability;
- security;
- testability;
- reliability for projects classified as active.

They are stored in project memory only after confirmation.

## Hard rules

`AGENTS.md` always contains the mandatory-rules section. Factoria does not invent project-specific hard rules during discovery. Organization and Factoria security restrictions continue to apply independently; project-specific rules can be added when they are actually confirmed.

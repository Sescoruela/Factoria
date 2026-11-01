# Trusted plugin discovery and loading

Factoria discovers plugins automatically from the paths configured in the global configuration. There is no separate plugin-install command.

Configured roots are read from `~/.factoria/config.toml`:

```toml
[plugins]
personal_paths = ["~/factoria-plugins"]
organization_paths = ["/opt/company/factoria-plugins"]
```

Built-in plugins, when present, are discovered from Factoria's own package.

## Priority

When multiple sources define the same plugin name, priority is:

1. personal;
2. organization;
3. built-in.

A higher-priority plugin shadows a lower-priority plugin and the shadowing is visible in `factoria plugins`.

If two plugins with the same name exist at the **same priority**, Factoria does not choose one arbitrarily. Both definitions are marked as errors and that name is blocked at that priority. A later unambiguous higher-priority definition may still take precedence.

## Manifest

Each plugin directory requires `plugin.toml`:

```toml
[plugin]
name = "my-checks"
version = "1.0.0"
type = "check"
description = "Custom project checks"
capabilities = ["example"]
entrypoint = "plugin.py"

[compatibility]
factoria = ">=0.2.0"
```

Supported plugin types are `adapter`, `pack`, `check` and `flow`.

The entrypoint must stay inside the plugin directory. `../` traversal outside that directory is rejected during manifest validation.

## Trusted-code boundary

A plugin entrypoint is **not sandboxed**. It is ordinary Python loaded into the Factoria process and can do anything the current user can do.

Configuring an external plugin directory is therefore an explicit trust decision. External executable plugins are shown with state `warning` even when their manifest is valid.

Executable entrypoints must expose:

```python
def load_plugin():
    return MyPlugin()
```

Factoria imports the module and calls `load_plugin()`. A missing factory, import exception or factory exception marks the plugin as an error and it is not loaded.

Plugins without an `entrypoint` are metadata-only and do not execute Python.

## States

- `valid`: manifest is valid and no warning applies;
- `warning`: plugin can load, but there is something the user should see (for example trusted external Python or deprecated manifest layout);
- `error`: plugin is not loaded.

## CLI

```bash
factoria plugins
```

The command automatically uses configured personal/organization paths and built-ins. Explicit extra roots remain available for diagnosis and development:

```bash
factoria plugins --personal ./local-plugins
factoria plugins --organization /tmp/org-plugins
factoria plugins --builtin ./builtin-plugins
```

The output lists loaded plugins, warnings, shadowed definitions and errors. It exits non-zero when discovery or loading errors remain.

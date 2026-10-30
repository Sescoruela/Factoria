# Configuración y plugins

## Configuración global

La configuración personal vive fuera de los repositorios, por ejemplo en `~/.factoria/config.toml`.

```toml
default_profile = "normal"
default_tool = "codex"

[plugins]
personal_paths = ["~/.factoria/plugins"]
organization_paths = []
```

## Configuración de proyecto

Cada repositorio puede definir `.factoria/config.toml` y sobrescribir valores heredables de la configuración global.

```toml
profile = "safe"

[flows]
allowed = ["fix", "feature", "memoria-update"]
blocked = []
```

La prioridad de resolución es configuración global, después configuración de proyecto y, en una fase posterior, opciones explícitas de CLI.

## Descubrimiento de plugins

Cada plugin vive en una carpeta propia y debe contener `plugin.toml`.

```toml
name = "example-checks"
version = "0.1.0"
type = "check"
description = "Comprobaciones adicionales de ejemplo"
capabilities = ["example"]

[compatibility]
factoria = ">=0.1.0"
```

Las fuentes tienen esta prioridad:

1. personal;
2. organización;
3. incluido con Factoria.

Un plugin de mayor prioridad puede sustituir a otro con el mismo nombre. Dos plugins con el mismo nombre y la misma prioridad bloquean el registro para evitar una elección silenciosa e impredecible.

Los manifests inválidos se registran con estado `error`; los manifests válidos con observaciones se registran con `warning` y pueden seguir cargándose.

Este hito implementa descubrimiento y resolución del registro. La carga de código Python del plugin y sus límites de ejecución se implementarán sobre este contrato en un hito posterior.

# Configuración y plugins

## Configuración global

La configuración personal vive fuera de los repositorios, por ejemplo en `~/.factoria/config.toml`.

```toml
default_profile = "normal"
default_tool = "codex"
max_agents = 2

[plugins]
personal_paths = ["~/.factoria/plugins"]
organization_paths = []
```

## Configuración de proyecto

Cada repositorio puede definir `.factoria/config.toml` y sobrescribir únicamente los valores heredables.

```toml
profile = "safe"
max_agents = 2

[flows]
allowed = ["fix", "feature", "memoria-update"]
blocked = []
```

Un proyecto no puede definir `default_tool`. La herramienta se decide de forma global o temporal por ejecución para que el repositorio siga siendo neutral respecto a Codex, OpenCode u otras herramientas.

La precedencia es: configuración global → proyecto → overrides temporales de ejecución.

## Descubrimiento de plugins

Cada plugin vive en una carpeta propia y debe contener `plugin.toml`.

Formato recomendado:

```toml
[plugin]
name = "example-checks"
version = "0.1.0"
type = "check"
description = "Comprobaciones adicionales de ejemplo"
capabilities = ["example"]
entrypoint = "plugin.py"

[compatibility]
factoria = ">=0.1.0,<1.0.0"
```

Tipos iniciales: `adapter`, `pack`, `check` y `flow`.

La jerarquía de fuentes es fija:

1. `personal`;
2. `organization`;
3. `builtin`.

Un plugin de mayor prioridad sustituye a otro con el mismo nombre y queda registrado cuál fue eclipsado. Dos plugins con el mismo nombre y la misma prioridad bloquean el registro.

Los manifests inválidos o incompatibles quedan registrados como problemas y no se cargan. El formato antiguo con campos del plugin en la raíz sigue siendo aceptado temporalmente, pero se marca como `warning`.

## Ejecución de plugins

La validación y resolución del registro se realiza antes de ejecutar código. Si el manifest declara `entrypoint`, Factoria puede cargar ese archivo Python después de la validación.

Los plugins son código de confianza: un entrypoint puede ejecutar Python arbitrario en el proceso actual. Añadir una ruta de plugins equivale a confiar en su contenido.

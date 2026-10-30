# Ejecución segura de verificaciones

Este hito conecta la planificación de calidad con la ejecución real de comandos confirmados por el proyecto.

## Principios

- `read_only` no ejecuta ningún comando del proyecto.
- `safe_checks` solo ejecuta comandos que ya están confirmados en la memoria del proyecto.
- Los comandos se ejecutan como `argv`, nunca mediante `shell=True`.
- No se infieren comandos nuevos durante la ejecución.
- Los checks se seleccionan según los módulos afectados y sus dependencias declaradas.
- Los checks marcados como globales se ejecutan siempre.
- Los checks obligatorios se traducen a `VerificationResult(required=True)`.
- Los fallos de arranque y timeouts se registran como verificaciones fallidas.

## Modelo de memoria

`ConfirmedCommand` añade metadatos explícitos a cada comando:

- `category`: `build`, `test`, `lint`, `typecheck`, `smoke` u otra categoría confirmada.
- `command`: argumentos exactos del proceso.
- `scope`: módulo al que pertenece, o `None` para un comando general.
- `required`: si su fallo debe bloquear el cierre.
- `global_check`: si debe ejecutarse siempre aunque no se detecte impacto directo en su módulo.

El formato antiguo `confirmed_commands` sigue siendo compatible temporalmente y se interpreta como comandos globales confirmados.

## Ejecución

`SafeCheckExecutor` recibe:

1. memoria del proyecto;
2. archivos modificados;
3. raíz del repositorio;
4. modo de ejecución;
5. categorías opcionales a ejecutar.

`CheckPlanner` determina los módulos afectados. Después se ejecutan únicamente los comandos confirmados que correspondan al plan.

`SubprocessCommandRunner` aplica timeout, captura salida y nunca abre un shell intermedio.

## Límites actuales

- Los comandos se ejecutan desde la raíz del proyecto; todavía no existe `cwd` específico por módulo.
- La salida se limita a los últimos 8000 caracteres por stream.
- Todavía no existe redacción avanzada de secretos en stdout/stderr; los informes no deben volcar estas salidas completas por defecto.
- La detección de comandos y su confirmación pertenece a un hito posterior de inicialización/CLI.

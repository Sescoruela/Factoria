# Ciclo persistente de memoria

Este hito permite reconstruir la memoria de un proyecto desde los archivos generados por Factoria y ejecutar `memoria-update` sin perder información confirmada.

## Carga segura

`load_project_memory()` interpreta únicamente el formato Markdown emitido por Factoria. Recupera:

- metadatos de revisión;
- propósito y tecnologías;
- módulos y relaciones `affects`;
- comandos confirmados, incluyendo scope y obligatoriedad;
- reglas obligatorias;
- dependencias;
- decisiones;
- pasos de verificación manual.

Si `AGENTS.md` no contiene una cabecera o estructura reconocible, la carga falla con `MemoryFormatError`. Factoria no intenta adivinar el contenido.

Los comandos se renderizan con quoting reversible mediante `shlex.join` y se reconstruyen con `shlex.split`.

## Staleness desde Git

`GitMemoryStalenessInspector` cuenta los commits entre `reviewed_commit` y `HEAD` y aplica los umbrales configurados por documento.

Los valores por defecto siguen siendo:

- arquitectura: 25 commits;
- flujos: 15 commits;
- decisiones: 50 commits;
- testing: 20 commits.

`.factoria/config.toml` puede sobrescribir cualquiera de estos umbrales.

Un documento marcado como stale no se modifica automáticamente. Se incluye como evidencia en la propuesta de `memoria-update` y requiere confirmación del usuario.

## `factoria memoria-update`

El comando ahora:

1. carga la memoria persistida;
2. valida el commit de última revisión;
3. calcula staleness;
4. vuelve a detectar tecnologías y módulos de forma conservadora;
5. conserva toda la información ya confirmada;
6. muestra motivo y evidencia de los cambios propuestos;
7. no escribe nada sin `--yes`;
8. respeta `--read-only` incluso si también se solicita una actualización.

Después de confirmar, actualiza la marca de revisión al `HEAD` actual y regenera los documentos de memoria.

## `factoria status`

`status` carga ahora la memoria real y muestra si alguno de sus documentos ha superado el umbral de revisión.

## Límites actuales

- El parser está diseñado para documentos generados por Factoria, no para Markdown arbitrario.
- La detección automática solo añade tecnologías o módulos nuevos; no elimina información confirmada.
- Un cambio semántico profundo de arquitectura sigue requiriendo revisión por agente/persona; el detector estructural no pretende inferirlo.

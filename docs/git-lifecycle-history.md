# Git lifecycle e historial local

Factoria no hace `push` ni abre pull requests automáticamente. El cierre de un flujo se mantiene bajo control humano.

## `factoria commit`

Cuando un flujo está en `ready_for_commit`, `factoria commit [flow_id]` prepara una vista previa con:

- rama actual;
- estado y ruta exacta de cada archivo pendiente;
- mensaje de commit propuesto.

Sin `--yes` no modifica el índice ni crea commits. El mensaje puede sustituirse con `--message`.

Con `--yes`, Factoria vuelve a comprobar que la rama y el árbol de trabajo no hayan cambiado desde la vista previa, hace `git add` únicamente de las rutas mostradas y crea el commit. Si después del commit queda cualquier cambio pendiente, el flujo no se considera cerrado.

Factoria rechaza commits de flujo directamente sobre `main`.

## Historial local

Al completar o cancelar un flujo desde la CLI, Factoria conserva un resumen y los artefactos relevantes en el directorio Git local resuelto mediante:

```text
git rev-parse --git-path factoria/history
```

Por tanto, el historial no forma parte del árbol versionado y no puede incluirse accidentalmente en un commit del proyecto.

Cada ejecución guarda, cuando existen:

- tarea;
- plan;
- verificación;
- review;
- propuesta de memoria;
- trazas de agentes;
- metadatos del flujo.

La retención es de un máximo de 50 ejecuciones y 30 días. Se aplica el límite que elimine antes el registro.

`factoria history` permite filtrar por tipo y estado y muestra número de ejecuciones, completadas/canceladas y duración media.

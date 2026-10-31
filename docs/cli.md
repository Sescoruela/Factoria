# CLI de Factoria

El paquete expone `factoria = factoria.cli:main` y también puede ejecutarse con `python -m factoria`.

## Comandos iniciales

- `factoria memoria-init`: analiza tecnologías, módulos y actividad Git, muestra la propuesta y solo escribe memoria con `--yes`.
- `factoria memoria-update`: comprueba que exista memoria. La reescritura estructurada queda pendiente del cargador de memoria.
- `factoria fix <titulo>`: crea un flujo `fix`, su workspace y `task.md`, y lo deja activo.
- `factoria feature <titulo>`: crea un flujo `feature`, su workspace y `task.md`, y lo deja activo.
- `factoria status`: muestra si hay memoria y los flujos incompletos.
- `factoria pause <flow_id> [--reason ...]`: pausa un flujo persistido.
- `factoria resume [flow_id]`: reanuda un flujo. Si solo hay uno incompleto, el id es opcional.
- `factoria cancel <flow_id> --yes`: cancela el flujo y elimina su workspace temporal. No elimina ramas Git.
- `factoria plugins`: descubre y lista plugins desde rutas suministradas con `--personal`, `--organization` o `--builtin`.

## Seguridad

`--read-only` bloquea cualquier operación que escriba memoria, cree workspaces o cambie estados de flujo.

La cancelación exige `--yes` antes de borrar artefactos temporales. La eliminación de ramas Git no forma parte todavía de esta versión del CLI.

## Ejemplos

```bash
factoria --project . status
factoria --project . memoria-init --name mi-proyecto
factoria --project . memoria-init --name mi-proyecto --yes
factoria --project . fix "Error al guardar cliente"
factoria --project . feature "Añadir login OAuth"
factoria --project . pause <flow-id> --reason "Esperando requisitos"
factoria --project . resume <flow-id>
factoria --project . cancel <flow-id> --yes
```

## Límites del hito

El CLI conecta la infraestructura ya existente y ofrece una interfaz estable, pero todavía no orquesta agentes reales ni crea ramas Git automáticamente. `memoria-update` aún no modifica archivos porque falta un cargador estructurado que reconstruya `ProjectMemory` desde la memoria persistida; se mantiene intencionadamente conservador para no sobrescribir documentación sin una representación fiable.

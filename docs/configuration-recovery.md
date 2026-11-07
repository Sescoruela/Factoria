# Esquemas, migración y recuperación (H13)

La sección **Recuperación**, disponible en ambas vistas, y `project config` permiten
revisar y confirmar operaciones sobre la configuración guardada. No hay migración
al abrir el proyecto ni restauraciones silenciosas.

## Versiones y migración

Sin `.factoria/schema.json` se reconoce el formato histórico **0**, compatible con
la lectura/edición existente. El esquema actual es **1**, marcado con
`{"schema_version": 1}`. Un marcador desconocido, corrupto, con claves duplicadas
o campos extra bloquea los lectores/editores de configuración; no se sustituye por
defaults ni se intenta una conversión especulativa. Relaciones muestra el error.

La migración 0→1 conserva los archivos legacy. Copia `ui-agents.json` y
`ui-workflows.json` a sus nombres compartidos si aún no existen, con los mismos
bytes, y crea el marcador. Si ambos catálogos contienen datos divergentes, el
preview bloquea la operación. No cambia modelos, permisos, memoria o proveedores.
Sobre esquema 1, migrar no vuelve a escribir ni crea otra copia.

## Revisar y confirmar

1. Seleccionar proyecto y operación: migrar, crear copia o restaurar una copia.
2. Revisar archivos cambiados/eliminados y conflictos. El preview no devuelve el
   contenido de instrucciones/skills ni escribe dentro del proyecto.
3. Confirmar la operación revisada. El token está ligado al proyecto, fuentes,
   operación y copia; cambios posteriores obligan a revisar otra vez.
4. Actualizar la aplicación tras finalizar para recargar los editores. Los paneles
   bloquean la operación si hay borradores y nunca los descartan automáticamente.

La restauración de una copia completa sustituye los archivos mostrados y puede
eliminar recursos creados después de la copia. La lista `removed` se muestra antes
de confirmar. No se reutiliza una copia de otro proyecto o movida a otro checkout.

## Copias y alcance

Las copias viven en la ruta local que devuelve
`git rev-parse --git-path factoria/config-recovery`, fuera de los archivos versionados
del proyecto. No se exportan con plantillas, no son una release ni una copia remota.
Para mantenerlas a largo plazo, respaldar también los metadatos Git de ese checkout.

Se capturan únicamente:

- Marcador, `.factoria/config.toml`, catálogos compartidos y legacy.
- Markdown de la carpeta plana `.factoria/skills/` con nombres alfanuméricos,
  guiones o guion bajo, y registros JSON del archivo H09.

Se excluyen memoria, archivos generados, instrucciones raíz, credenciales de
máquina, `.factoria/work/` e historial Git. Los snapshots de ejecuciones activas
conservan sus bytes aunque se restaure el catálogo. La integración generada puede
quedar desactualizada: revisar y preparar ambas herramientas por el mecanismo
habitual, sin arrancar ni autenticar proveedores.

Las fuentes se validan con los parsers existentes y se examinan con el detector
local de posibles secretos antes de copiar. Un hallazgo bloquea la operación;
no se copia el secreto ni se muestra su valor. Este detector no garantiza identificar
todo dato sensible: mantener las credenciales fuera de los archivos compartidos.

Límites: 2 MiB por archivo, 8 MiB acumulados, 2048 entradas por carpeta y 256 copias
locales. Se rechazan symlinks, rutas fuera del inventario, formatos incompatibles,
copias corruptas y fuentes que exceden los límites. No se purgan copias automáticamente;
si se alcanza el límite, archivarlas manualmente antes de continuar.

## Interrupciones

Antes de escribir se guarda un journal `pending` con bytes anteriores/previstos y
hashes de integridad. Las escrituras individuales usan reemplazo y flush/fsync;
en POSIX también se sincroniza el directorio. Al completar, el journal pasa a
`complete`. No se presenta esto como una transacción universal frente a fallos de
hardware o sistemas de archivos: se ha comprobado recuperación ante errores e
interrupciones de proceso simulados, no cortes de alimentación reales.

Ante una operación pendiente:

1. Las nuevas escrituras de catálogos, plantillas, ciclo de vida e integración se bloquean.
2. Consultar **Actualizar copias** o `project config status`.
3. Revisar y confirmar **Restaurar** esa copia. Si algún archivo cambió externamente
   y ya no coincide con los bytes anteriores ni previstos, se bloquea la restauración
   conservando ese cambio; resolverlo manualmente y revisar de nuevo.
4. Al recuperar, el journal pasa a `restored` y se permiten nuevas ediciones.

Una recuperación interrumpida puede reintentarse con otro preview. Las copias
completadas se restauran mediante una nueva operación recuperable, conservando a
su vez el estado previo a la restauración. La política vigente debe permitir
escritura; una política ilegible o restrictiva exige resolución manual y no se omite.

Los journals históricos de importación H08 o archivo H09 no se convierten ni se
restauran automáticamente: sus formatos carecen de los mismos datos de propiedad
para decidir qué bytes sustituir. Conservarlos y seguir su recuperación manual.
Crear un checkpoint H13 antes de operaciones de riesgo permite volver al inventario
completo revisado. Los guardados normales no crean checkpoints automáticamente.

## CLI

```bash
factoria --project /ruta/proyecto project config status
factoria --project /ruta/proyecto --read-only project config migrate
factoria --project /ruta/proyecto project config migrate --yes --token TOKEN_DEL_PREVIEW
factoria --project /ruta/proyecto project config snapshot
factoria --project /ruta/proyecto project config snapshot --yes --token TOKEN_DEL_PREVIEW
factoria --project /ruta/proyecto project config restore ID_COPIA
factoria --project /ruta/proyecto project config restore ID_COPIA --yes --token TOKEN_DEL_PREVIEW
```

Sin `--yes`, las tres operaciones solo previsualizan. `--read-only` permite status
y previews; rechaza la aplicación. La API autenticada exige el proyecto seleccionado
para `/api/config/status`, `/preview` y `/apply`, con confirmación explícita al aplicar.
Las copias validadas pueden usar una carpeta temporal fuera del proyecto para
comprobar sus parsers. No se añaden dependencias de runtime.

## Evidencia — 07/11/2026

16 pruebas H13: migración legacy exacta, idempotencia, checkpoints/restauración con
eliminaciones revisadas, tokens, permisos, versiones desconocidas, catálogos
conflictivos, fallos de escritura/proceso, recuperación interrumpida y reintento,
cambios externos, límites, secretos, symlinks, corrupción, concurrencia, CLI y
API autenticada de ambos shells. También se conserva una snapshot nativa real y
sus archivos de memoria durante migración/restauración.

Dos recorridos Chromium nuevos prueban migrar/copiar/modificar/restaurar desde
ambas interfaces. Cifras de suite completa y límites en [estado vigente](project-status.md).
Actions sigue deshabilitado: sin CI remoto, Windows ni aceptación externa nueva.
H05/H06 y H11 continúan abiertos; esta entrega no publica la versión 0.3.0.

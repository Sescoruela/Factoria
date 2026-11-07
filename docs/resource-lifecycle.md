# Duplicar, archivar y restaurar recursos (H09)

Disponible en **Archivo de recursos** de ambos shells web y en la CLI. Opera sobre
skills gestionadas, agentes y workflows del proyecto; no inicia proveedores ni
cambia memoria, políticas, comandos, autenticación o configuración de máquina.

## Desde la aplicación

1. Seleccionar proyecto y guardar o descartar borradores de los editores.
2. Abrir **Archivo de recursos** y **Recargar recursos**.
3. Elegir operación y recurso. Para duplicar, indicar un identificador nuevo y,
   opcionalmente, un nombre. La copia conserva las referencias originales;
   duplicar un agente no duplica sus skills ni reasigna sus consumidores.
4. Pulsar **Ver impacto**. Revisar proyecto, identificador, bloqueos y snapshots
   existentes. Los básicos se duplican, pero no se archivan.
5. Confirmar solo si no hay bloqueos. Revisar el diff en Git y preparar ambas
   herramientas después: la integración no se regenera automáticamente.

Cambiar proyecto, selección, contenido de catálogos, archivo de recursos o nuevas
snapshots relevantes invalida el preview. Se conserva la revisión optimista de los
editores y no se aceptan guardados anteriores a un archivado/restauración.

## Referencias y orden

| Recurso | Qué bloquea su archivado | Restauración |
| --- | --- | --- |
| Skill gestionada | Referencias de agentes activos, incluidas rutas equivalentes | Recupera exactamente el Markdown y metadatos guardados |
| Agente propio | Referencias de etapas de workflows activos | Requiere skills disponibles y rol base válido |
| Workflow propio | No bloquea por snapshots ya congeladas | Requiere agentes compatibles con los roles de sus etapas |
| Agentes básicos y fix/feature | Protegidos; no se archivan | Personalizar mediante copia con ID nuevo |

No hay cascada ni reasignación automática. Archivar primero el workflow, después
su agente sin referencias y finalmente su skill. Restaurar en el orden inverso.
Si un recurso tiene otros consumidores, retirarlos explícitamente antes.

Las snapshots y el historial de ejecuciones existentes no se reescriben ni borran.
La retención normal del historial de ejecuciones no cambia. El archivado modifica
archivos del proyecto: un flujo activo conserva su definición, pero sus controles
de árbol/código, verificación y aprobación siguen aplicándose; no se saltan gates.

Los identificadores archivados quedan reservados. Los editores y las plantillas
H08 no pueden recrearlos ni añadir referencias a dependencias archivadas. Restaurar
falla si existe un recurso/ruta incompatible, faltan dependencias o el registro fue
alterado de forma incoherente. No se sobrescribe el recurso que ocupa la ruta.
Archivos Markdown ajenos al catálogo no se archivan ni se sustituyen.

## Terminal

```bash
factoria --project /ruta/proyecto project resources list
factoria --project /ruta/proyecto project resources duplicate agent reviewer --new-id reviewer-api --name "Revisor API"
# Revisar el preview y copiar su token:
factoria --project /ruta/proyecto project resources duplicate agent reviewer --new-id reviewer-api --name "Revisor API" --yes --token "TOKEN_DEL_PREVIEW"
factoria --project /ruta/proyecto project resources archive workflow fix-api
# Aplicar repitiendo con --yes --token del preview revisado.
factoria --project /ruta/proyecto project resources restore workflow ID_DE_ARCHIVO
```

`restore` recibe el `archive_id` de 32 caracteres mostrado por `list`, no el ID del
workflow. Toda escritura exige preview, token vigente y confirmación. Sin `--yes`
no cambia el proyecto. `--read-only` permite listar/previsualizar, pero bloquea
duplicar/archivar/restaurar con confirmación. Se respeta la política WRITE vigente.
Los identificadores usan las reglas actuales del catálogo: workflows hasta 48
caracteres; skills/agentes hasta 64. Se bloquean colisiones, rutas inseguras y
secretos detectables; el detector no garantiza identificar todo dato privado.

## Persistencia y fallos

El registro versionable vive en `.factoria/archive/<archive_id>.json` y conserva
la definición, contenido original y fechas/estado de la operación. Restaurar no
borra el registro. Las entradas duplicadas documentan el origen de la copia.
Revisar esos archivos antes de compartirlos igual que cualquier instrucción del proyecto.

Antes de modificar el catálogo se crea un registro `pending`; el archivo activo
usa creación exclusiva o reemplazo atómico. Se conservan las otras entradas y los
formatos locales antiguos; los catálogos JSON pueden normalizar su presentación.
Ante un fallo se intenta restaurar el contenido anterior. Si una edición externa
posterior impide la restauración, se conserva y el error señala el registro a revisar.
No hay garantía de transacción de varios archivos frente a una caída del proceso
o equipo. Un registro `pending` o una copia incoherente requiere revisión manual:
conservar cambios externos, revisar el diff y el contenido original, sin borrar
toda `.factoria`. La recuperación automática y migraciones siguen en H13.

## Evidencia — 07/11/2026

368 tests completos correctos, Linux/Python 3.12.14, incluidos 17 de H09. Cubren
los tres tipos, básicos, unicidad, dependencias y roles, rutas equivalentes,
restauración exacta, reservas en editores/H08, fallos y ediciones externas,
concurrencia, tokens/snapshots, historial real de una ejecución cancelada,
políticas/read-only, CLI y API autenticada de ambos shells.

`node tests/ui/resources_controller_smoke.cjs` verifica el controlador con DOM/API
simulados: cambios de selección/proyecto, confirmación/cancelación, bloqueos,
restauración y preview asíncrono. No es prueba visual ni de navegador real.
Sintaxis JS y recurso del wheel comprobados. No se afirma CI remoto, Windows ni
aceptación de proveedores nuevos; Actions permanece deshabilitado. H05/H06 siguen abiertos.

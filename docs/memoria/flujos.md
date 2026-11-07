<!-- factoria-memory: type=active | reviewed_commit=999bb373751a8cc7445dfe5ad5381809d2517028 | date=2026-11-07 | factoria=0.3.0 -->
# Flujos

## memoria-init y memoria-update
La inicialización propone tecnologías, módulos, comandos y tipo de proyecto. Solo
escribe tras confirmación. La actualización conserva datos confirmados y el bloque
de integración de AGENTS.md; requiere regenerar los assets si cambia la memoria.

## Preparación del proyecto

**Relaciones** o `project relations` permite revisar workflow → etapa → agente →
skills, recursos sin ruta activa, referencias rotas/archivadas e integración.
La consulta no escribe; actualizarla no reemplaza borradores. Abrir un editor exige
proyecto/revisión vigentes y ausencia de borradores o guardados pendientes.

**Archivo de recursos** o `project resources` permite duplicar, previsualizar
impacto, archivar y restaurar con confirmación y token vigente. Las referencias
activas bloquean archivo; restauración exige dependencias compatibles. Los básicos
solo se duplican; los IDs archivados se reservan. Después revisar diff y regenerar
integración. Snapshots e historial anteriores no se modifican.

Para reutilizar recursos entre proyectos, exportar una plantilla, elegir destino,
previsualizar y confirmar con el token revisado. Los conflictos bloquean toda la
importación y no se copian memoria/políticas/comandos. Después revisar el diff y
preparar la integración. Ver [plantillas](../project-templates.md).
`project prepare` valida configuración y genera una propuesta para Codex y OpenCode.
Con `--yes` escribe solo si no hay conflictos. `project check` comprueba vigencia.

## Uso directo
Las guías piden a Codex/OpenCode leer AGENTS.md y seleccionar `factoria-fix`,
`factoria-feature` o un workflow propio. La selección natural depende del agente
y su aceptación desde una sesión nueva sigue pendiente. `native start` congela el flujo y la memoria; `native next`
comprueba evidencia, aprobaciones, verificación y review antes de avanzar.
Pausa, reanudación y cancelación conservan código y ramas. El cierre exige árbol
limpio con el contenido verificado y archiva el resultado.

## Uso orquestado opcional
`factoria fix/feature` ejecuta agentes por adaptadores. Feature/fix grande requieren
plan y aprobación final; fix pequeño sigue su ruta acotada. Verificación, review
estructurada, commit confirmado e historial se gestionan por los servicios existentes.

## Estado de aceptación
Fix y feature del host con checkout están completados con aprobaciones y commits
locales. No prueban aislamiento de modelos, descubrimiento natural ni sesiones
externas autenticadas. H05 mantiene esas comprobaciones pendientes.
H06 tiene paquetes y upgrade Python comprobados; Windows y release siguen pendientes.
Actions está deshabilitado hasta nuevo aviso. Ver [estado vigente](../project-status.md)
y [criterios de cierre](../mvp-checklist.md).

## H11 · Cambios externos de proyecto

Actualizar tras seleccionar otro proyecto en otra pestaña conserva los borradores
de skills, agentes y workflows. El formulario de agente valida el origen antes de
guardar; regresar al proyecto original o descartar requiere una acción explícita.
Los conflictos conservan la versión guardada por la otra pestaña y el borrador local.

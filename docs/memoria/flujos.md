<!-- factoria-memory: type=active | reviewed_commit=e23d54381c460f37b8ade59bbdcb267f2bbfe366 | date=2026-11-06 | factoria=0.3.0 -->
# Flujos

## memoria-init y memoria-update
La inicialización propone tecnologías, módulos, comandos y tipo de proyecto. Solo
escribe tras confirmación. La actualización conserva datos confirmados y el bloque
de integración de AGENTS.md; requiere regenerar los assets si cambia la memoria.

## Preparación del proyecto
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

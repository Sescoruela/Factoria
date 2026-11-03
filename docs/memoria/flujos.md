<!-- factoria-memory: type=active | reviewed_commit=1a2e02c9692177fb5c7d63a10efa70379b5dca17 | date=2026-11-03 | factoria=0.2.0 -->
# Flujos

## memoria-init y memoria-update
La inicialización propone tecnologías, módulos, comandos y tipo de proyecto. Solo
escribe tras confirmación. La actualización conserva datos confirmados y el bloque
de integración de AGENTS.md; requiere regenerar los assets si cambia la memoria.

## Preparación del proyecto
`project prepare` valida configuración y genera una propuesta para Codex y OpenCode.
Con `--yes` escribe solo si no hay conflictos. `project check` comprueba vigencia.

## Uso directo
Codex/OpenCode carga AGENTS.md y selecciona la skill `factoria-fix` o
`factoria-feature`. `native start` congela el flujo y la memoria; `native next`
comprueba evidencia, aprobaciones, verificación y review antes de avanzar.
Pausa, reanudación y cancelación conservan código y ramas. El cierre exige árbol
limpio con el contenido verificado y archiva el resultado.

## Uso orquestado opcional
`factoria fix/feature` ejecuta agentes por adaptadores. Feature/fix grande requieren
plan y aprobación final; fix pequeño sigue su ruta acotada. Verificación, review
estructurada, commit confirmado e historial se gestionan por los servicios existentes.

## Estado de aceptación
Hay pruebas deterministas de los recorridos. La validación autenticada en las dos
herramientas y el CI de esta entrega se registran en `docs/mvp-checklist.md`.

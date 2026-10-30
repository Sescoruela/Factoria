# Flujo `fix`

El flujo `fix` convierte las decisiones de producto del MVP en reglas de dominio verificables.

## Secuencia

1. **Reproducir** el fallo antes de modificar código.
2. **Analizar** el alcance estimado.
3. Si supera los límites configurados, promocionarlo a fix grande y exigir aprobación del plan.
4. **Implementar** el cambio mínimo.
5. **Verificar** usando únicamente comprobaciones disponibles en el proyecto.
6. **Revisar** objetivo, criterios de aceptación y reglas obligatorias.
7. Corregir hallazgos bloqueantes y volver a verificar/revisar hasta el límite configurado.
8. Cerrar directamente un fix pequeño o pedir aprobación final si se promocionó a fix grande.

## Evidencia de reproducción

La reproducción es obligatoria y se registra en uno de estos formatos, por orden de preferencia cuando sea viable:

- `automated_test`: infraestructura de tests existente;
- `script`: script reproducible sin crear infraestructura de tests como efecto lateral;
- `manual`: pasos manuales exactos.

## Límites

`FixLimits` define inicialmente:

- máximo de archivos modificados;
- máximo de líneas modificadas;
- máximo de ciclos automáticos revisión/corrección.

Los límites son configuración de la factoría, no una medida objetiva de complejidad. Superarlos activa la gobernanza de cambio grande.

## Verificación

Una verificación obligatoria fallida bloquea inmediatamente el flujo. Las opcionales se registran pero no bloquean por sí solas.

## Revisión

El revisor usa tres severidades:

- `critical`: bloquea;
- `important`: bloquea;
- `minor`: informa.

También bloquean las violaciones de reglas obligatorias y los criterios de aceptación no cumplidos. Los hallazgos bloqueantes provocan un nuevo ciclo de corrección mientras queden reintentos disponibles.

## Informe

`FixReportRenderer` genera un informe de texto estructurado con secciones estables:

1. Summary
2. Reproduction
3. Changes
4. Verification
5. Review
6. Decisions
7. Permissions
8. Final status

La integración con agentes, Git y ejecución real de comandos se conectará mediante adaptadores en hitos posteriores.

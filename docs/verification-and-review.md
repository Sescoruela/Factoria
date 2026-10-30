# Verificación y review reutilizables

Este hito extrae las reglas comunes de calidad de los flujos `fix` y `feature`.

## VerificationGate

Recibe resultados de verificación y bloquea el cierre cuando falla cualquier check marcado como obligatorio. Los checks opcionales pueden fallar sin bloquear el flujo, pero siguen apareciendo en el informe.

## ReviewGate

Centraliza la política de findings:

- `critical` e `important` bloquean.
- `minor` informa, pero no bloquea.
- `fix` puede entrar en ciclos de corrección hasta el máximo configurado.
- `feature` usa la misma decisión de review, pero actualmente bloquea directamente y requiere intervención antes de continuar.

## CheckPlanner

Selecciona verificaciones según los archivos modificados y la memoria del proyecto:

1. Detecta módulos afectados usando `ModuleMemory.paths`.
2. Propaga impacto por `ModuleMemory.affects`.
3. Selecciona checks cuyo `scope` corresponde a un módulo afectado.
4. Incluye siempre los checks marcados como globales.

Esto permite que un cambio en `frontend/` no ejecute checks exclusivos de `backend/`, salvo que exista una relación de impacto o se trate de un check global.

## Límites del hito

Este hito define planificación y decisiones de calidad. La ejecución real de comandos confirmados (`build`, `test`, `lint`, `typecheck`, `smoke`) se conectará en el siguiente nivel de infraestructura/adaptadores. No se inventan comandos que no estén confirmados en la memoria del proyecto.

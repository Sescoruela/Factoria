# Roadmap de Factoria

Seguimiento general: [issue #6](https://github.com/Sescoruela/Factoria/issues/6). Plan acordado el 05/11/2026.
Los nueve hitos originales del editor permanecen en [issue #2](https://github.com/Sescoruela/Factoria/issues/2) y `editor-milestones.md`.

## Objetivo

Configurar toda la estructura de trabajo del proyecto desde Factoria y consumirla desde Codex/OpenCode iniciados externamente. No iniciar ni autenticar proveedores desde la aplicación.

## Hitos y dependencias

Los esfuerzos son orientativos; no hay fechas comprometidas. Cada enlace contiene los criterios de aceptación completos.

| Hito | Entrega | Fase / prioridad | Estado | Dependencias | Esfuerzo |
| --- | --- | --- | --- | --- | --- |
| [H01 #7](https://github.com/Sescoruela/Factoria/issues/7) | Guardado seguro de workflows | MVP / P0 | Completado en PR #20 | Ninguna | 0,5–1 día |
| [H02 #8](https://github.com/Sescoruela/Factoria/issues/8) | Catálogo y editor de skills | MVP / P1 | Completado en PR #21 | H01 | 2–3 días |
| [H03 #9](https://github.com/Sescoruela/Factoria/issues/9) | Asignar agentes propios a etapas | MVP / P1 | Completado en PR #22 | H01, H02 | 1–2 días |
| [H04 #10](https://github.com/Sescoruela/Factoria/issues/10) | Workflows con nombre propio | MVP / P1 | Completado en PR #23 | H01, H03 | 2–4 días |
| [H05 #11](https://github.com/Sescoruela/Factoria/issues/11) | Aceptación real en Codex y OpenCode | MVP / P1 | En curso: host parcial; CLIs y aprobaciones pendientes | H02, H03, H04 | 1–2 días según incidencias |
| [H06 #12](https://github.com/Sescoruela/Factoria/issues/12) | Primera versión distribuible y actualización | MVP / P1 | Pendiente | H05, H07 | 0,5–1 día |
| [H07 #13](https://github.com/Sescoruela/Factoria/issues/13) | Documentación y estado verificable | MVP / P1 | Parcial: documentación actualizada; seguimiento continuo | Ninguna | 0,5 día inicial y actualización continua |
| [H08 #14](https://github.com/Sescoruela/Factoria/issues/14) | Plantillas reutilizables entre proyectos | Posterior / P2 | Pendiente | H04, H06 | Por estimar |
| [H09 #15](https://github.com/Sescoruela/Factoria/issues/15) | Duplicar y archivar recursos | Posterior / P2 | Pendiente | H02, H03, H04 | Por estimar |
| [H10 #16](https://github.com/Sescoruela/Factoria/issues/16) | Vista de relaciones del proyecto | Posterior / P2 | Pendiente | H02, H03, H04 | Por estimar |
| [H11 #17](https://github.com/Sescoruela/Factoria/issues/17) | Pruebas de navegador en CI | Posterior / P2 | Pendiente | H02, H04 | Por estimar |
| [H12 #18](https://github.com/Sescoruela/Factoria/issues/18) | Simplificar el frontend | Posterior / P2 | Pendiente | H11 | Por estimar |
| [H13 #19](https://github.com/Sescoruela/Factoria/issues/19) | Migraciones y recuperación de configuración | Posterior / P2 | Pendiente | H04, H06 | Por estimar |

## Secuencia

H01 → H02 → H03 → H04 → H05 → H06. H07 acompaña cada entrega y se cierra antes de la release. H08–H13 son mejoras posteriores; no bloquean el MVP.

## Cierre verificable

Crear skill → asignarla a un agente propio → incluirlo en un workflow → guardar → cerrar/reabrir → preparar las dos herramientas → iniciar externamente → ejecutar fix y feature con aprobaciones y evidencia. Registrar la aceptación autenticada por separado de las pruebas deterministas.

H01 solo se cierra con pruebas de conflictos, escritura atómica, borradores e identidad de proyecto y CI verde. No declarar completado el editor de skills ni los workflows propios por la existencia de agentes personalizados.

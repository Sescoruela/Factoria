# Changelog

## 0.3.0 — Preparación, sin release publicada

- Interfaz clara con navegación por tareas, resumen del proyecto, formularios de agentes/skills en dos columnas, menú móvil y conexiones del diagrama alineadas. Los enlaces a editores conservan el destino al retirar el token de la URL.

- Refactor transversal: formato consistente, contratos neutros de rutas y persistencia, recursos compartidos, separación CLI/API, límites de capas y consulta común de borradores.

- H13: esquema 1 explícito, migración revisada de catálogos legacy, checkpoints locales y restauración con integridad, journal pendiente y bloqueo de ediciones tras interrupciones. Web y CLI, sin migraciones automáticas.

- H12: assets JS/CSS, sesión/API y composición de estado compartidos; interfaz principal definida y borradores de agentes respetados en paneles auxiliares.

- Smoke de navegador real con 22 casos y workflow de informes/trazas (H11; CI pendiente con Actions deshabilitado). Conservación de autenticación al recargar, catálogos tras guardar workflows y borradores de agente ante cambios externos de proyecto.

- Vista navegable de relaciones workflow/etapa/agente/skills con diagnóstico de referencias, huérfanos e integración y conservación de borradores (H10).

- Duplicación, archivado reversible y restauración web/CLI de recursos con preview de referencias, reserva de identificadores e historial conservado (H09).

- Plantillas JSON portables de skills, agentes y workflows: exportación, preview, conflictos e importación confirmada desde web/CLI; recuperación local ante fallos.

- Catálogos de skills y agentes: crear, editar y guardar con revisiones y escritura atómica.
- Agentes propios asignados a etapas y workflows con nombre basados en fix/feature.
- Integración compartida para Codex y OpenCode, iniciados externamente; snapshots y aprobaciones humanas.
- Detección de raíz del proyecto para evitar duplicar sus subcarpetas.
- Metadatos de release incluidos en el paquete y comprobación offline de SHA-256.
- El ejecutable dirige la actualización al instalador; no intenta ejecutarse como Python/pip.
- Documentación de instalación, actualización y conservación de configuración.

Documentación H07 reconciliada; [estado verificable](docs/project-status.md).
Pendientes para etiquetar/publicar: H05 (aceptación externa), validación del
instalador y actualización entre versiones en Windows, CI multiplataforma y descarga
de los artefactos finales. Actions está deshabilitado por petición del usuario.
Los binarios de pruebas no tienen firma Authenticode. Esta preparación no certifica el MVP.

## 0.2.0 — Base de desarrollo anterior

Infraestructura de flujos, memoria, políticas, actualización/rollback por commit
verificado e instalador por usuario. Esta entrada describe la base del código;
no afirma que exista una release pública etiquetada ni aceptación en proveedores.

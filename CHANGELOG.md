# Changelog

## 0.3.0 — Preparación, sin release publicada

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

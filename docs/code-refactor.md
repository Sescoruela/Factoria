# Refactor transversal — 07/11/2026

La entrega separa el formato mecánico de la reorganización de responsabilidades.
No cambia los comandos, esquemas persistidos, autorizaciones ni el arranque externo
de proveedores. H05/H06/H11 mantienen sus comprobaciones pendientes y Actions
permanece deshabilitado.

## Estructura resultante

| Responsabilidad | Ubicación |
| --- | --- |
| Rutas contenidas en el proyecto, symlinks y unidades Windows | `factoria/project_paths.py` |
| Staging y publicación de bytes, creación exclusiva y sincronización | `factoria/storage.py` |
| Parseo del marcador de esquema | `factoria/config/schema.py` |
| Bloqueo de escritura por esquema/recuperación pendiente | `application/config_schema.py` |
| Bloqueos compartidos y su orden | `application/resource_locks.py` |
| Serialización de recursos, hashes, revisión y detección de secretos | `application/resource_support.py` |
| Contrato `MemoryChange` | `domain/models.py` |
| Parser y acciones CLI independientes | `project_cli.py` |
| Endpoints de editores | `web_editor_api.py` |
| Endpoints de recursos, plantillas, relaciones y recuperación | `web_project_api.py` |
| Composición de estado | `web_editor_state.py` |
| Arranque del servidor local y autenticación | `web_app.py`, reutilizado por ambos shells |
| Consulta compartida de borradores/guardados | `web/editor-state.js` |

Configuración y memoria ya no importan servicios de aplicación. Las comprobaciones
arquitectónicas impiden volver a introducir esas dependencias. Los imports antiguos
de `project_integration.project_path`, `application.config_schema.schema_version`
y `application.memory_flows.MemoryChange` siguen disponibles por compatibilidad.

Los servicios de archivo/relaciones/recuperación dejan de depender de utilidades
privadas de plantillas. Las escrituras compartidas dejan al consumidor la política,
validación de rutas, revisión optimista y journal: la primitiva de bytes no concede
permisos ni constituye una transacción multiarchivo.

El staging elimina temporales incluso si falla el flush antes de publicar. Agentes,
workflows, skills, plantillas, archivo y recuperación lo reutilizan conservando sus
comprobaciones de revisión, creación exclusiva y recuperación. Los tests existentes
de disco/concurrencia siguen verificando esos contratos.

## Formato y herramientas

Se aplica un estilo consistente a Python de `src/`, `tools/` y `packaging/` y a los
assets JS/CSS/HTML. En la primera pasada mecánica se compararon los árboles
sintácticos de 105 módulos Python y de todos los JS existentes: ninguna diferencia.
Las extracciones posteriores son un commit separado para poder revisar su lógica.
La capa de dominio y los adaptadores mantienen sus algoritmos; el refactor de
responsabilidades se concentra en los acoplamientos y duplicaciones encontrados.

Ruff 0.14.4 y Prettier 3.6.2 son herramientas opcionales de desarrollo, fijadas en
metadatos/lockfile; el runtime Python conserva `dependencies = []`.

```bash
python -m pip install -e '.[dev]'
ruff format --check src tools packaging
ruff check src tools packaging
npm ci --prefix tests/ui/browser --ignore-scripts --no-audit --no-fund
npm --prefix tests/ui/browser run format:check
python -m unittest discover -s tests
```

Para aplicar formato: `ruff format src tools packaging` y
`npm --prefix tests/ui/browser run format`. El lint configurado comprueba sintaxis,
referencias indefinidas y variables usadas antes de asignarse; no es un análisis de
tipos completo ni una auditoría de seguridad.

## Evidencia

- Baseline: 398 unittest y 25/25 Chromium correctos.
- Pasada solo de formato: 398 unittest y 25/25 Chromium correctos; AST sin cambios.
- Resultado final: **406 unittest** y **25/25 Chromium reales** correctos localmente,
  sin reintentos ni saltos del navegador.
- Cinco contratos nuevos de persistencia (bytes exactos, no sobrescritura exclusiva,
  fallo al publicar/flush y revisión rechazada tras staging) y tres de arquitectura/
  compatibilidad de imports.
- Controladores de Relaciones/Plantillas/Archivo con DOM/API simulados correctos.
- Formato, lint, sintaxis, enlaces y contenido/instalación del wheel comprobados.

Resumen con versiones y hashes en
[refactor-local-evidence.json](acceptance/refactor-local-evidence.json).
Navegador local: Chromium headless 153.0.8010.0 temporal con Playwright 1.62.1.
Sin CI remoto, Windows, auditoría visual/accesibilidad ni aceptación nueva de LLM.
No se presenta un refactor como prueba de cierre del MVP o como una release publicada.

<!-- factoria-memory: type=active | reviewed_commit=a73de1abbf011a9a16b99a1e7859cd1908d7e3d7 | date=2026-11-06 | factoria=0.3.0 -->
# Verificación y pruebas

## H08 · Plantillas reutilizables

`test_project_templates.py` añade 16 pruebas de export/import, equivalencia en un
repositorio nuevo, ambas integraciones, conflictos/idempotencia, tokens de preview,
concurrencia, políticas, secretos/rutas, fallos de escritura/restauración, snapshots,
CLI y autenticación API de ambos shells. Suite local H08: 351 tests correctos,
Linux/Python 3.12.14. Sintaxis de templates.js y recurso del wheel comprobados.
No hay CI/Windows nuevos; Actions deshabilitado. El navegador disponible rechazó
conexión al laboratorio local, por lo que no se afirma validación visual.

## Estado
- Framework: unittest, biblioteca estándar.
- Comando confirmado: `python -m unittest discover -s tests`.
- La suite cubre dominio, políticas, memoria, adaptadores, flujos, Git, plugins, UI e historial.
- `test_agent_catalog.py` cubre catálogo propio, compatibilidad, API autenticada, referencias, guardado atómico y conflictos entre editores; las pruebas no inician proveedores.
- `test_project_integration.py` comprueba exportación para ambas herramientas y recorridos directos en repositorios temporales, también por CLI pública.
- CI configurado para Ubuntu Python 3.11–3.13 y Windows/macOS Python 3.11.
- El instalador Windows tiene un pipeline separado de build, instalación y desinstalación.

## Cómo comprobarlo a mano
1. Instalar el paquete con Python 3.11+ en un entorno virtual.
2. Ejecutar la suite completa.
3. Preparar un repositorio de prueba desde Integración y revisar el diff.
4. Seguir el recorrido real de `docs/direct-project-integration.md` en ambas herramientas.
5. Registrar versiones, modelos, aprobaciones y bloqueos en `docs/mvp-checklist.md`.

## Límites de las pruebas
Las pruebas no usan modelos remotos. No demuestran descubrimiento de skills por un
LLM, autenticación de proveedores ni disponibilidad de shell en Codex/ChatGPT.
El fixture POSIX de agente orquestado se omite en Windows; las pruebas del recorrido
directo por CLI se ejecutan allí. No declarar CI remoto o aceptación real superados
sin revisar su resultado correspondiente.

## Editor de agentes

En un repositorio temporal, abrir **Agentes**, crear un identificador propio y
asignarle una skill Markdown existente. Guardar, reabrir y modificarlo. Comprobar
que editar un agente básico conserva los personalizados. Verificar que refrescar
no borra un borrador, que **Descartar / recargar** lo elimina y que cambiar de
proyecto pide confirmación. Con un borrador abierto, editar `agents.json` desde
fuera: el guardado debe avisar del conflicto y conservar ambas versiones. Preparar
la integración y revisar el catálogo, el contexto portable y los archivos OpenCode.

## Guardado de workflows (H01)

`test_workflow_persistence.py` cubre guardados atrasados y simultáneos, cambios externos durante la escritura, fallo de reemplazo, migración, JSON inválido, symlinks y API autenticada con proyecto/revisión. `test_project_integration.py` comprueba que editar workflows no altera la snapshot activa. Ambas interfaces conservan el borrador tras un conflicto y permiten recargar con confirmación. La aceptación real en proveedores continúa pendiente.

## Editor de skills (H02)

`test_skill_catalog.py` comprueba persistencia exacta, referencias, propiedad de archivos,
concurrencia, fallos de disco, secretos, políticas, symlinks, API y exportación. La suite
de integración verifica que editar una skill no altera la snapshot del flujo activo.

Smoke opcional de DOM/API con Node y jsdom (solo desarrollo; no es una prueba de
navegador real): instalar jsdom en una carpeta temporal y ejecutar
`NODE_PATH=<carpeta>/node_modules python tests/ui/run_skills_smoke.py`. Usa repositorios
y preferencias temporales y cubre creación, edición, reapertura, conflictos, cambio
de proyecto, selector de agentes y preparación de ambas herramientas. H11 conserva
la tarea de automatizar pruebas con navegador real en CI.

## H03 · Asignación de agentes a etapas

`test_workflow_agent_assignment.py` verifica compatibilidad de roles, herencia y
overrides, referencias inexistentes, cambios concurrentes de catálogo, compatibilidad
con formatos antiguos, prompts congelados del modo avanzado, API y guías de ambas
herramientas. Los tests nativos cubren fix/feature en ambos modos de herramienta,
aprobaciones bloqueantes, cambio explícito de plataforma y snapshots independientes
de cambios posteriores en agente, workflow o skill. No llaman a proveedores LLM.

Smoke DOM/API opcional: `NODE_PATH=<carpeta>/node_modules python tests/ui/run_skills_smoke.py --workflow-agents`.
Requiere Node y jsdom de desarrollo; cubre ambos shells, catálogo actualizado,
selección compatible, guardado, reapertura y conflictos. H11 sigue reservando
la automatización de pruebas con navegador real en CI.

## H04 · Workflows propios

`test_named_workflows.py` cubre catálogo completo, edición y creación, duplicados,
identificadores portables, conservación del resto de recursos, migración, políticas,
secretos, referencias, API, exportación y conflictos. Los recorridos nativos prueban
fix/feature propios con aprobaciones para ambos modos de herramienta, selección por
CLI pública, allowlists/bloqueos y snapshots actuales/antiguas.

Smoke opcional DOM/API para ambos shells:
`NODE_PATH=<carpeta>/node_modules python tests/ui/run_skills_smoke.py --named-workflows`.
Verifica formularios, base fija, guardado, reapertura, agentes, duplicados,
borradores, conflictos y recursos generados. No es aceptación con navegador real
ni con un proveedor autenticado: H05/H11 continúan separados.

## H05 · Laboratorio de aceptación

`tools/acceptance_lab.py` es una herramienta de desarrollo externa a la UI. Prepara
repositorios aislados de fix/feature para tres entornos y permite inspeccionar
artefactos. Su preflight solo lee presencia en PATH. No ejecuta ni autentica
proveedores y no emite aceptación automática.

`test_acceptance_lab.py` cubre aislamiento, protección de destinos existentes,
baselines, estado parcial, approvals y el caso mecánico completo que sigue
requiriendo revisión humana. Esos tests no prueban uso real de proveedores.
El protocolo y la evidencia parcial están en `docs/acceptance/`; H05 permanece
abierto hasta observar y revisar las sesiones, versiones/modelos y aprobaciones.

## H06 · Distribución y actualización

`test_release_artifacts.py` comprueba versión/metadatos, hashes, corrupción,
archivos ausentes, manifiestos inválidos, duplicados/traversal y bloqueo del updater
Python en ejecutables frozen. `tools/distribution_smoke.py` instala dos wheels
locales en un venv/HOME aislados, prepara un proyecto con recursos propios y
comprueba actualización y dos reaperturas sin cambios en los datos.
Evidencias y límites: [estado H06](../release-h06-status.md).
Actions está deshabilitado hasta nuevo aviso: no declarar CI o instalador Windows
superados para esta entrega a partir de los tests locales.

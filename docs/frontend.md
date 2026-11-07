# Frontend mantenible (H12)

La interfaz principal es `index_n8n.html`, servida por el entrypoint web habitual y
por `/editors`. La raíz del servidor clásico sigue disponible por compatibilidad;
no es una segunda implementación de los servicios de edición.

JavaScript y CSS son recursos estáticos incluidos en el wheel:

- `shell-common.js`: sesión local, cliente HTTP, escape y avisos compartidos.
- `shell-main.js/css`, `shell-classic.js/css`: presentación y adaptadores de cada vista.
- `agents.js/css`: editor de agentes e integración, antes incrustados en Python.
- `workflows.js`, `skills.js`, `templates.js`, `resources.js`, `relations.js`: paneles.

`web_shell.py` carga el HTML sin inyectar código. `web_editor_state.py` compone los
catálogos completos para ambos shells; `web_editor_api.py` sirve sus endpoints
autenticados. Ninguno depende de heredar el handler de una presentación específica.
La lista cerrada de assets evita servir rutas arbitrarias e incluye MIME CSS/JS.

Los borradores de agente exponen el mismo contrato de consulta que los de skills;
Relaciones/Plantillas/Archivo respetan ese estado. No se inicia ni autentica ningún
proveedor desde la aplicación. Python mantiene runtime de biblioteca estándar.

Evidencia local 07/11/2026: suite Python y recorridos Chromium completos, incluido
un caso nuevo que conserva un borrador de agente al intentar navegar desde Relaciones.
Consultar [estado vigente](project-status.md) para cifras. H11 sigue abierto por CI:
Actions permanece deshabilitado. Esta refactorización no cierra H05/H06.

Tras el refactor transversal, `editor-state.js` centraliza la consulta de borradores
para los paneles. `web_project_api.py` agrupa recursos/plantillas/relaciones/recuperación
y ambos shells comparten el arranque en `serve_web_ui`. [Detalle](code-refactor.md).

La capa `interface.css/js` comparte el tema, la navegación por tareas y el resumen
real del proyecto. [Capturas, uso y comprobaciones de la interfaz](interface-refresh.md).

# Frontend mantenible (H12)

La interfaz principal es `index_n8n.html`, servida por el entrypoint web habitual y
por `/editors`. La raíz del servidor clásico sigue disponible por compatibilidad;
no es una segunda implementación de los servicios de edición.

El código web vive en `src/factoria/web/`. El paquete `frontend/` contiene
HTML, JavaScript y CSS y se incluye en la distribución de Factoría. Las dos
vistas llaman a la misma API HTTP local mediante `/api/…`. El backend sirve
los recursos públicos mediante `/assets/…`.

- `shell-common.js`: sesión local, cliente HTTP, escape y avisos compartidos.
- `shell-main.js/css`, `shell-classic.js/css`: presentación y adaptadores de cada vista.
- `agents.js/css`: editor de agentes e integración, antes incrustados en Python.
- `workflows.js`, `skills.js`, `templates.js`, `resources.js`, `relations.js`: paneles.

En `backend/`, `server.py` sirve el HTML, valida el token de sesión y limita
las rutas públicas a los assets autorizados. `editor_state.py` compone el estado
compartido y `editor_api.py` y `project_api.py` atienden las peticiones de edición
y gestión de proyectos. El backend delega las operaciones en `application/`.

Los borradores de agente exponen el mismo contrato de consulta que los de skills;
Relaciones/Plantillas/Archivo respetan ese estado. No se inicia ni autentica ningún
proveedor desde la aplicación. Python mantiene runtime de biblioteca estándar.

El primer recorrido local del 07/11/2026 incluyó un caso que conserva un borrador
de agente al navegar desde Relaciones. `editor-state.js` centraliza la consulta de
borradores para los paneles. [Estructura y verificación](code-refactor.md).

La capa `interface.css/js` comparte el tema, la navegación por tareas y el resumen
real del proyecto. [Capturas, uso y comprobaciones de la interfaz](interface-refresh.md).

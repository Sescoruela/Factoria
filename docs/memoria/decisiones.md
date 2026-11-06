<!-- factoria-memory: type=active | reviewed_commit=e23d54381c460f37b8ade59bbdcb267f2bbfe366 | date=2026-11-06 | factoria=0.3.0 -->
# Decisiones

- La memoria y configuración compartida viven junto al código del proyecto.
- Factoría gestiona la estructura; Codex/OpenCode son las interfaces principales del LLM.
- Ambas integraciones forman parte del MVP desde el principio.
- Los roles básicos son explorer, planner, implementer, reviewer y documenter.
- Agentes y flujos se guardan en JSON versionable; políticas en TOML e instrucciones en Markdown.
- Se importan configuraciones locales anteriores sin borrarlas ni ignorar errores.
- El modo directo registra etapas y ejecuta comprobaciones sin otra llamada LLM.
- El modelo y los permisos de una sesión externa permanecen bajo control de su herramienta.
- Las snapshots preservan flujos e instrucciones de las ejecuciones en curso.
- La regeneración bloquea conflictos y conserva el contenido propio de AGENTS.md.
- El commit requiere autorización; push y PR permanecen manuales en el producto.
- Las pruebas deterministas no equivalen a aceptación con modelos reales.
- El núcleo usa Python 3.11+ y biblioteca estándar en runtime.
- La firma de binarios y distribución amplia se difieren hasta disponer de certificado.

- La aplicación no inicia ni diagnostica proveedores: Codex/OpenCode se arrancan externamente.
- Añadir/modificar/guardar skills, agentes y workflows propios está implementado; la aceptación conjunta sigue en H05/#2.
- Las cifras de pruebas se registran con fecha, plataforma y alcance; el [estado vigente](../project-status.md) enlaza evidencias y límites.
- 0.3.0 es preparación de código; no se declara release publicada. El ejecutable frozen dirige update/rollback al instalador, sin pip.
- Actions se deshabilitó por petición del usuario y solo se reactiva cuando lo indique.

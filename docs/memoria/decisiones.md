<!-- factoria-memory: type=active | reviewed_commit=1a2e02c9692177fb5c7d63a10efa70379b5dca17 | date=2026-11-03 | factoria=0.2.0 -->
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

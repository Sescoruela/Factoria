<!-- factoria-memory: type=active | reviewed_commit=e06933195e3231bebacbe25aacaf19f529dc2164 | date=2026-11-07 | factoria=0.3.0 -->
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
- H10 diagnostica sin reparar ni ejecutar: fuentes rotas producen mapa parcial, no defaults inventados. Los huérfanos requieren información suficiente. Navegar a editores vuelve a comprobar revisión/proyecto y bloquea si hay borradores; el shell clásico reutiliza el editor completo en otra pestaña local.
- H09 no archiva básicos ni elimina referencias automáticamente: primero se retiran consumidores. Conserva snapshots/historial y reserva IDs archivados hasta restaurar. La copia de recuperación no sustituye una transacción frente a caídas ni cierra H13.
- H08 comparte recursos mediante JSON v1 cerrado, sin memoria, políticas ni configuración de máquina. Se reutilizan idénticos; conflictos bloquean sin sobrescritura. La copia local permite recuperación manual; no se promete transacción multiarchivo ante caídas (H13).

## H11 · Estado y sesión web

Las respuestas compartidas de API conservan catálogos de skills/agentes e
integración, también al guardar workflows. La pestaña conserva el token local en
`sessionStorage` para recargar sin dejarlo en la URL; no inicia ni autentica
proveedores. Node/Playwright son solo desarrollo. La evidencia Chromium local no
cierra H11 hasta observar CI, con Actions deshabilitado.

## H13 · Recuperación explícita

El formato histórico 0 sigue siendo legible; migrar a 1 requiere preview y
confirmación. Esquemas desconocidos bloquean lectores y escritores. Los journals
H13 guardan bytes/hashes antes de escribir y bloquean nuevas ediciones si quedan
pendientes. Recuperar no pisa cambios externos ajenos. Los journals antiguos H08/H09
no se adoptan automáticamente; checkpoints H13 son operaciones explícitas.

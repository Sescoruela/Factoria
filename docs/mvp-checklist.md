# Cierre del MVP

## Objetivo acordado

Configurar y mantener la estructura completa de trabajo de cada proyecto desde
Factoría, para usar sus agentes, instrucciones, skills, memoria y flujos directamente
desde Codex u OpenCode. El LLM se utiliza principalmente en esas herramientas.

## Criterios y evidencia

| Hito | Estado en esta entrega | Evidencia |
| --- | --- | --- |
| Configuración compartida por proyecto | Implementado | `agents.json`, `workflows.json`, `config.toml`; migración de configuración local anterior |
| Instrucciones y skills por rol | Implementado | Editor web, validación de rutas y propagación a uso directo/orquestado |
| Preparación para ambas herramientas | Implementado | Skills compartidas, comandos y agentes OpenCode, bloque de entrada en AGENTS.md |
| Seguimiento sin otra sesión LLM | Implementado | CLI `native`; fix/feature, snapshots, evidencia, pausas, aprobaciones y cierre |
| Verificación y review bloqueantes | Implementado | Comandos confirmados, alternativa manual y contrato JSON de review |
| Regeneración conservadora | Implementado | Preview, hashes, conflictos, preservación de AGENTS.md y retirada de assets deshabilitados |
| Pruebas deterministas | 244 pruebas superadas localmente, Python 3.12 / Linux | `tests/test_project_integration.py` y suite existente |
| CI multiplataforma | Configurado; resultado de ejecución registrado en GitHub | Ubuntu Python 3.11–3.13; Windows/macOS Python 3.11 |
| Instalador Windows | Pipeline existente; resultado de build registrado en GitHub | Build, instalación, smoke de versión y desinstalación en CI |
| Aceptación con Codex autenticado | Pendiente | Ejecutar el recorrido real documentado |
| Aceptación con OpenCode autenticado | Pendiente | Ejecutar el recorrido real documentado |
| Codex/ChatGPT con checkout | Pendiente de validar en el entorno elegido | Comprobar acceso a archivos y CLI, y comportamiento ante ausencia de herramientas |
| ChatGPT sin checkout | Contexto portable implementado | Modo propuesta; no equivale a ejecución de flujos |

El estado «implementado» significa que existe código y una comprobación determinista;
no demuestra aceptación con un proveedor remoto. El cierre funcional completo requiere
la aceptación real en ambas herramientas y CI verde sobre el cambio revisado.

## Fuera del MVP

- Firma Authenticode y distribución amplia: requiere certificado y custodia de firma.
- Invocar APIs LLM propias o custodiar credenciales de proveedores dentro de Factoría.
- Flujos arbitrarios con ramificaciones, agentes personalizados fuera de los cinco roles,
  selección automática del modelo de una sesión externa o aislamiento no provisto por ella.
- Stash automático, push/PR automáticos, catálogo central de proyectos y métricas inventadas.

## Registro de aceptación real

| Entorno | Versión herramienta/modelo | Fix | Feature y aprobaciones | Bloqueos | Resultado |
| --- | --- | --- | --- | --- | --- |
| Codex local | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| OpenCode local | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| Codex/ChatGPT con repositorio | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |

## Verificación local de esta entrega · 03/11/2026

- Suite completa: **244 pruebas, OK** (`python -m unittest discover -s tests`).
- Sintaxis del JavaScript de la nueva interfaz: comprobada con `node --check`.
- Diff: sin errores de whitespace con `git diff --check`.
- Runtime: sin nuevas dependencias externas obligatorias.
- Codex/OpenCode no están instalados en el entorno de esta revisión; no se han
  ejecutado sesiones autenticadas ni se ha validado el enrutado natural por un LLM.
- CI y build Windows de esta entrega: consultar los resultados del [PR #1](https://github.com/Sescoruela/Factoria/pull/1).

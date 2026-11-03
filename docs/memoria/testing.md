<!-- factoria-memory: type=active | reviewed_commit=1a2e02c9692177fb5c7d63a10efa70379b5dca17 | date=2026-11-03 | factoria=0.2.0 -->
# Verificación y pruebas

## Estado
- Framework: unittest, biblioteca estándar.
- Comando confirmado: `python -m unittest discover -s tests`.
- La suite cubre dominio, políticas, memoria, adaptadores, flujos, Git, plugins, UI e historial.
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

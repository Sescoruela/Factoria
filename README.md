# Factoria

Factoria configura y mantiene la estructura de una factoría de software por proyecto: agentes, instrucciones, skills, flujos, políticas y memoria. El trabajo con LLM se realiza principalmente en **Codex o OpenCode**, con la autenticación, modelos y permisos de esas herramientas.

El recorrido principal es **configurar en Factoria → preparar el proyecto para ambas herramientas → abrir Codex/OpenCode → pedir una corrección o funcionalidad → seguir el flujo configurado**. La aplicación puede permanecer cerrada durante ese trabajo. El CLI local de Factoria conserva el seguimiento y ejecuta las comprobaciones confirmadas, sin iniciar un segundo LLM.

El inicio, autenticación y diagnóstico de Codex/OpenCode se hacen fuera de la aplicación. El panel usa detección pasiva y guarda preferencias sin arrancar sus ejecutables. El modo avanzado `factoria fix/feature` sigue disponible únicamente al invocarlo explícitamente desde una terminal externa.

> Estado al 06/11/2026: código 0.3.0 preparado, sin release publicada. Editores implementados; aceptación externa H05 y distribución H06 pendientes. Actions deshabilitado hasta nuevo aviso. Ver [estado verificable](docs/project-status.md) y [criterios de cierre](docs/mvp-checklist.md).

## Inicio rápido

### Windows

El pipeline de Windows está preparado para generar dos artefactos. El instalador
0.3.0 todavía no está validado ni publicado; esta sección describe su uso previsto:

- `Factoria.exe`: ejecutable standalone; no requiere Python instalado.
- `Factoria-Setup-<version>.exe`: instalador por usuario, sin permisos de administrador.

El instalador instala Factoria en `%LOCALAPPDATA%\Programs\Factoria`, crea accesos del menú Inicio y ofrece añadir el directorio de instalación al `PATH` del usuario. El desinstalador elimina únicamente la entrada de Factoria que haya añadido al `PATH`.

Tras instalar, abre una terminal nueva y ejecuta:

```powershell
factoria
```

La primera ejecución abre la interfaz web local. La terminal interactiva está disponible con `factoria tui` y el onboarding con `factoria onboarding`. Codex/OpenCode no se incluyen dentro del instalador: Factoria solo muestra detección pasiva; debes iniciarlos y autenticarlos fuera de la aplicación.

Los instaladores generados por CI todavía no están firmados digitalmente. La firma Authenticode queda fuera del MVP y debe añadirse antes de distribuir binarios como release de confianza amplia.

### Python / desarrollo

Requisitos: Python 3.11+ y Git. Desde un checkout de Factoria, crea un entorno
virtual y actívalo (`source .venv/bin/activate` en Linux/macOS;
`.\.venv\Scripts\Activate.ps1` en PowerShell). Después instala el proyecto:

```bash
python -m venv .venv
# Activar el entorno virtual antes de los siguientes comandos.
python -m pip install -e .
factoria
```

Ejecutar `factoria` sin argumentos abre la interfaz web local en el navegador. También puedes abrirla explícitamente:

```bash
factoria ui
```

Puedes abrir el onboarding de terminal cuando necesites una guía:

```bash
factoria onboarding
```

El onboarding explica el modelo de trabajo, permite preparar la memoria y muestra
presencia pasiva de herramientas. No inicia, autentica ni ejecuta diagnósticos de
Codex/OpenCode; esos pasos se hacen externamente.

## Uso principal: trabajar desde Codex u OpenCode

1. Selecciona el proyecto en la aplicación e inicializa su memoria.
2. Configura sus skills y agentes; en el diseñador selecciona el agente compatible para cada etapa. Puedes sobrescribir perfil y plataforma por etapa.
3. Abre **Integración**, revisa los cambios y pulsa **Preparar ambas herramientas**.
4. Revisa y guarda los archivos del proyecto en Git; selecciona una rama de trabajo.
5. Abre Codex u OpenCode en el repositorio. Puedes cerrar la aplicación de Factoria.
6. Pide «corrige este error» o «añade esta funcionalidad». `AGENTS.md` contiene la
   instrucción para seleccionar `factoria-fix` o `factoria-feature`; su cumplimiento
   depende del agente anfitrión y sigue pendiente de aceptación en una sesión nueva.
   Si la intención o el workflow son ambiguos, se aclaran primero.
7. Como selección explícita, usa `$factoria-fix` / `$factoria-feature` en Codex,
   o `/factoria-fix` / `/factoria-feature` en OpenCode.
8. La herramienta sigue las etapas con `factoria native`, registra evidencia, espera
   las aprobaciones requeridas y ejecuta las verificaciones confirmadas.
9. Revisa el resultado y autoriza el commit. Push y PR continúan siendo manuales.

### Workflows propios

En **Diseñador de flujo**, elige una plantilla en **Crear a partir de**, pulsa
**Crear workflow** y completa identificador, nombre y descripción. Conserva el tipo
base y sus controles; selecciona agentes compatibles, guarda y prepara la integración.

Ejemplo: `fix-api`, basado en `fix`. Selección explícita:

```bash
factoria project workflows
factoria native start fix-api --tool codex --task "Corregir contrato HTTP"
# En OpenCode, usar --tool opencode.
```

También se generan `$factoria-fix-api` para Codex y `/factoria-fix-api` para OpenCode.
Si la petición natural admite varios workflows, hay que aclarar cuál utilizar.
El bloqueo del tipo base también bloquea sus variantes; una allowlist puede seleccionar
un identificador propio, pero no anula un bloqueo.

La configuración común vive en `.factoria/agents.json`, `.factoria/workflows.json`
y `.factoria/config.toml`. La preparación importa las antiguas configuraciones locales
`ui-agents.json` y `ui-workflows.json` si no hay configuración común, y no las borra.

Desde terminal, el equivalente a la preparación es:

```bash
factoria project prepare        # preview, sin escritura
factoria project prepare --yes  # generar tras revisar
factoria project check         # comprobar vigencia y conflictos
```

Los archivos generados llevan un manifiesto de hashes. La regeneración conserva
el contenido propio de `AGENTS.md` y bloquea si detecta cambios manuales en otros
archivos generados. Regenera tras cambiar agentes, flujos, skills o memoria.

### Codex dentro de ChatGPT y ChatGPT sin repositorio

Codex/ChatGPT con acceso al checkout puede consumir las instrucciones y skills del
repositorio. Para ejecutar el seguimiento necesita acceso al CLI de Factoria y a Git.
Una conversación de ChatGPT sin ese acceso no puede descubrir archivos de tu equipo:
adjunta `.factoria/generated/chatgpt-context.md` y el código necesario. Ese modo
permite propuestas; no afirma ejecución, permisos aplicados ni pruebas superadas.

Consulta [integración directa](docs/direct-project-integration.md) para límites y
recorridos reproducibles. No se instalan plugins personales ni se modifican los
archivos globales de Codex/OpenCode.

## Comandos principales

```text
factoria                     # abre la UI
factoria ui                  # interfaz web local
factoria tui                 # interfaz de terminal
factoria project prepare     # preview de integración con ambas herramientas
factoria project check       # vigencia de la integración
factoria native start ...    # seguimiento dentro de Codex/OpenCode, sin otro LLM
factoria onboarding          # guía interactiva
factoria status              # diagnóstico operativo
factoria memoria-init        # propuesta de memoria
factoria feature ...         # flujo feature
factoria fix ...             # flujo fix
factoria resume ...          # reanudar/aprobar un flujo
factoria commit ...          # preview + confirmación de commit
factoria history             # historial local
factoria security incidents  # incidentes persistentes de secretos
factoria plugins             # plugins descubiertos
factoria update              # actualización por release etiquetada
```

## Principios del MVP

- Nunca implementar directamente sobre `main`.
- Commit solo con confirmación explícita; push y PR manuales.
- Los secretos bloquean independientemente del perfil de permisos.
- Sin verificación automatizada confirmada, Factoria exige una vía manual explícita.
- Los perfiles de modelo son abstractos (`rapido`, `equilibrado`, `potente`) y deben mapearse a modelos concretos.
- La memoria y el análisis de impacto no inventan estado de repositorios o servicios externos.
- La UI no relaja ninguna política del núcleo: solo guía las mismas operaciones gobernadas del CLI.

## Portabilidad

La versión 0.3.0 está en preparación; todavía no es una release publicada ni un MVP
aceptado. Instalación, actualización y checksums: [procedimiento de release](docs/release-process.md).
GitHub Actions permanece deshabilitado hasta nuevo aviso.

El runtime principal se mantiene sin dependencias externas obligatorias. Las interfaces web local y de terminal usan únicamente la biblioteca estándar de Python y funciona como una capa sobre los mismos servicios y comandos del núcleo.

En Windows, PyInstaller empaqueta ese runtime en un único `Factoria.exe`; Inno Setup envuelve el ejecutable en un instalador por usuario. Las dependencias de build (`pyinstaller` e Inno Setup) solo son necesarias en CI/desarrollo, no en el equipo del usuario final.

## Próximos hitos del editor

Los nueve hitos de añadir, modificar y guardar **skills, agentes y workflows** están definidos con estado, dependencias y criterios de aceptación en [hitos del editor](docs/editor-milestones.md). El catálogo de agentes propios ya permite crear, modificar y guardar; el catálogo de skills también permite crear, modificar y guardar. El diseñador permite asignar agentes propios a etapas compatibles. El diseñador también permite crear y guardar workflows con identificador propio basados en fix o feature. La aceptación real con herramientas autenticadas sigue pendiente. El [roadmap completo](docs/roadmap.md) separa el cierre del MVP de las mejoras posteriores.

## Aceptación real (H05)

El [protocolo de aceptación](docs/acceptance/h05-protocol.md) prepara casos de fix y
feature en repositorios aislados, con registro de versiones, modelos y aprobaciones.
El [estado observado](docs/acceptance/h05-status.md) es parcial: las pruebas de
código/CI no equivalen a aceptación autenticada. El laboratorio no inicia ni
autentica Codex/OpenCode desde la aplicación.

## Guías y evidencia

- [Estado vigente y límites](docs/project-status.md).
- [Uso de skills, agentes y workflows](docs/editor-milestones.md).
- [Exportar e importar plantillas entre proyectos](docs/project-templates.md).
- [Duplicar, archivar y restaurar recursos](docs/resource-lifecycle.md).
- [Mapa de relaciones, diagnóstico y navegación a editores](docs/project-relations.md).
- [Pruebas de navegador y CI pendiente (H11)](docs/browser-smoke.md)
- [Estructura del frontend (H12)](docs/frontend.md)
- [Migración y recuperación de configuración (H13)](docs/configuration-recovery.md)
- [CLI y seguimiento directo](docs/cli.md).
- [Instalación, actualización e integridad](docs/release-process.md).
- [Roadmap y siguientes hitos](docs/roadmap.md).

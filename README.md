# Factoria

Factoria configura y mantiene la estructura de una factoría de software por proyecto: agentes, instrucciones, skills, flujos, políticas y memoria. El trabajo con LLM se realiza principalmente en **Codex o OpenCode**, con la autenticación, modelos y permisos de esas herramientas.

El recorrido principal es **configurar en Factoria → preparar el proyecto para ambas herramientas → abrir Codex/OpenCode → pedir una corrección o funcionalidad → seguir el flujo configurado**. La aplicación puede permanecer cerrada durante ese trabajo. El CLI local de Factoria conserva el seguimiento y ejecuta las comprobaciones confirmadas, sin iniciar un segundo LLM.

También se conserva el modo opcional orquestado: `factoria fix/feature` lanza agentes mediante sus adaptadores.

> Estado: implementación del MVP con pruebas deterministas; la aceptación con instalaciones reales de Codex/OpenCode se registra por separado. Ver [criterios de cierre](docs/mvp-checklist.md).

## Inicio rápido

### Windows

La distribución de Windows genera dos artefactos:

- `Factoria.exe`: ejecutable standalone; no requiere Python instalado.
- `Factoria-Setup-<version>.exe`: instalador por usuario, sin permisos de administrador.

El instalador instala Factoria en `%LOCALAPPDATA%\Programs\Factoria`, crea accesos del menú Inicio y ofrece añadir el directorio de instalación al `PATH` del usuario. El desinstalador elimina únicamente la entrada de Factoria que haya añadido al `PATH`.

Tras instalar, abre una terminal nueva y ejecuta:

```powershell
factoria
```

La primera ejecución abre la interfaz web local. La terminal interactiva está disponible con `factoria tui` y el onboarding con `factoria onboarding`. Codex/OpenCode no se incluyen dentro del instalador: Factoria los detecta y valida durante el onboarding.

Los instaladores generados por CI todavía no están firmados digitalmente. La firma Authenticode queda fuera del MVP y debe añadirse antes de distribuir binarios como release de confianza amplia.

### Python / desarrollo

Requisitos: Python 3.11+ y un repositorio Git.

```bash
python -m pip install -e .
factoria
```

Ejecutar `factoria` sin argumentos abre la interfaz web local en el navegador. También puedes abrirla explícitamente:

```bash
factoria ui
```

La primera vez, Factoria ofrece un onboarding guiado. Puedes repetirlo cuando quieras:

```bash
factoria onboarding
```

El onboarding explica el modelo de trabajo, permite preparar la memoria del repositorio, ejecuta el diagnóstico seguro de herramientas y enseña el recorrido de una feature/fix sin saltarse ninguna confirmación.

## Uso principal: trabajar desde Codex u OpenCode

1. Selecciona el proyecto en la aplicación e inicializa su memoria.
2. Configura sus agentes (perfil, plataforma, instrucciones y rutas de skills) y flujos.
3. Abre **Integración**, revisa los cambios y pulsa **Preparar ambas herramientas**.
4. Revisa y guarda los archivos del proyecto en Git; selecciona una rama de trabajo.
5. Abre Codex u OpenCode en el repositorio. Puedes cerrar la aplicación de Factoria.
6. Pide «corrige este error» o «añade esta funcionalidad». `AGENTS.md` dirige la petición
   a `factoria-fix` o `factoria-feature`; si la intención es ambigua, se aclara primero.
7. Como selección explícita, usa `$factoria-fix` / `$factoria-feature` en Codex,
   o `/factoria-fix` / `/factoria-feature` en OpenCode.
8. La herramienta sigue las etapas con `factoria native`, registra evidencia, espera
   las aprobaciones requeridas y ejecuta las verificaciones confirmadas.
9. Revisa el resultado y autoriza el commit. Push y PR continúan siendo manuales.

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

El runtime principal se mantiene sin dependencias externas obligatorias. Las interfaces web local y de terminal usan únicamente la biblioteca estándar de Python y funciona como una capa sobre los mismos servicios y comandos del núcleo.

En Windows, PyInstaller empaqueta ese runtime en un único `Factoria.exe`; Inno Setup envuelve el ejecutable en un instalador por usuario. Las dependencias de build (`pyinstaller` e Inno Setup) solo son necesarias en CI/desarrollo, no en el equipo del usuario final.

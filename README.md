# Factoria

Factoria es una fábrica portable de flujos de desarrollo asistidos por agentes. Mantiene memoria por repositorio, aplica permisos y políticas, coordina Codex/OpenCode, ejecuta verificaciones confirmadas, estructura el review y deja trazabilidad local de cada ejecución.

> Estado: MVP funcional con CLI, TUI interactiva, onboarding, seguridad, historial, instalador Windows y validación end-to-end hermética.

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

La primera ejecución abre la TUI y ofrece el onboarding guiado. Codex/OpenCode no se incluyen dentro del instalador: Factoria los detecta y valida durante el onboarding.

Los instaladores generados por CI todavía no están firmados digitalmente. La firma Authenticode queda fuera del MVP y debe añadirse antes de distribuir binarios como release de confianza amplia.

### Python / desarrollo

Requisitos: Python 3.11+ y un repositorio Git.

```bash
python -m pip install -e .
factoria
```

Ejecutar `factoria` sin argumentos abre la UI interactiva. También puedes abrirla explícitamente:

```bash
factoria ui
```

La primera vez, Factoria ofrece un onboarding guiado. Puedes repetirlo cuando quieras:

```bash
factoria onboarding
```

El onboarding explica el modelo de trabajo, permite preparar la memoria del repositorio, ejecuta el diagnóstico seguro de herramientas y enseña el recorrido de una feature/fix sin saltarse ninguna confirmación.

## Flujo habitual

1. Inicializa/revisa la memoria del proyecto.
2. Mantén `main` limpio.
3. Lanza una feature o fix desde la UI o el CLI.
4. Revisa y aprueba el plan cuando corresponda.
5. Factoria implementa, verifica y revisa el cambio con las políticas configuradas.
6. Revisa el resultado final y el preview del commit.
7. Confirma el commit explícitamente.
8. Push y PR siguen siendo manuales por diseño.

## Comandos principales

```text
factoria                     # abre la UI
factoria ui                  # abre la UI
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

El runtime principal se mantiene sin dependencias externas obligatorias. La TUI usa únicamente la biblioteca estándar de Python y funciona como una capa sobre los mismos servicios y comandos del núcleo.

En Windows, PyInstaller empaqueta ese runtime en un único `Factoria.exe`; Inno Setup envuelve el ejecutable en un instalador por usuario. Las dependencias de build (`pyinstaller` e Inno Setup) solo son necesarias en CI/desarrollo, no en el equipo del usuario final.

# Instalador de Factoria para Windows

## Objetivo

El MVP de Windows debe poder instalarse sin que el usuario tenga que instalar Python ni ejecutar `pip` manualmente. El pipeline genera dos binarios:

- `Factoria.exe`: ejecutable standalone construido con PyInstaller.
- `Factoria-Setup-<version>.exe`: instalador por usuario construido con Inno Setup.

La versión se lee de `pyproject.toml`, que sigue siendo la fuente canónica del paquete.

## Comportamiento del instalador

El instalador:

1. No requiere permisos de administrador (`PrivilegesRequired=lowest`).
2. Instala por defecto en `%LOCALAPPDATA%\Programs\Factoria`.
3. Crea accesos en el menú Inicio.
4. Permite añadir Factoria al `PATH` del usuario.
5. Registra únicamente el directorio añadido por Factoria y lo retira al desinstalar.
6. No instala Codex ni OpenCode; el onboarding de Factoria detecta y valida esas herramientas por separado.

Después de instalar y abrir una terminal nueva:

```powershell
factoria
```

abre la TUI y el onboarding del MVP.

## Build reproducible en CI

El workflow `.github/workflows/windows-installer.yml` usa `windows-latest` y Python 3.12 para:

1. instalar Factoria en modo editable para el build;
2. instalar PyInstaller;
3. construir `Factoria.exe` con metadata del paquete y datos del adapter;
4. ejecutar `Factoria.exe --version` como smoke test;
5. compilar el instalador con Inno Setup;
6. instalarlo silenciosamente en un directorio temporal;
7. ejecutar el binario instalado y validar la versión;
8. desinstalarlo silenciosamente;
9. subir ambos `.exe` como artefacto de GitHub Actions.

El ejecutable final no necesita Python instalado en la máquina del usuario.

## Seguridad y límites del MVP

Los binarios producidos por CI no están firmados con Authenticode. Windows SmartScreen puede mostrar una advertencia al ejecutar un binario descargado por primera vez. La firma digital requiere un certificado de code signing y gestión segura de la clave privada; no se incluye una clave ni se simula una firma en el repositorio.

Antes de una distribución más amplia se recomienda:

- adquirir/configurar un certificado de firma de código;
- firmar `Factoria.exe` y `Factoria-Setup-<version>.exe` en CI usando un secreto gestionado fuera del repositorio;
- verificar la firma después del build;
- publicar hashes SHA-256 junto a cada release.

El instalador tampoco incorpora Git ni los CLIs de los proveedores. Factoria sigue requiriendo un repositorio Git para operar y un adapter disponible cuando se quiera ejecutar un flujo con agentes reales.

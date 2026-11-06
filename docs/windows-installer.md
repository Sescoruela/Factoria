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
6. No instala ni inicia Codex/OpenCode; la aplicación detecta su presencia y el usuario los inicia externamente.

Después de instalar y abrir una terminal nueva:

```powershell
factoria
```

abre la interfaz web local. `factoria tui` abre la interfaz de terminal.

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

El instalador tampoco incorpora Git ni los CLIs de los proveedores. El modo directo
requiere un repositorio Git y se consume desde Codex/OpenCode iniciados externamente.

## Actualización y estado H06

Cerrar Factoria y ejecutar el nuevo instalador en la misma carpeta. No guardar
proyectos dentro de la carpeta del programa. Antes de actualizar, respaldar los
proyectos completos y `%USERPROFILE%\.factoria`. No desinstalar para actualizar.
El ejecutable no utiliza `pip` para actualizarse ni aplica migraciones automáticas.
Para volver atrás se necesita el instalador anterior verificado y la copia de datos.

El pipeline preparado incluye reinstalación/reapertura de un proyecto configurado y
`SHA256SUMS` junto al instalador y ejecutable. No sustituye una actualización desde
el binario anterior ni una prueba visual. Actions está deshabilitado por petición
del usuario; estos cambios aún no se han ejecutado en Windows. Ver el
[procedimiento de release e integridad](release-process.md).

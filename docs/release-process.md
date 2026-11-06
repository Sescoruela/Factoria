# Preparar y verificar una distribución

Estado al 06/11/2026: versión de código **0.3.0 preparada**, sin tag ni release.
Actions permanece deshabilitado hasta nuevo aviso. H06 continúa abierto por H05,
Windows, CI y publicación. H07 mantiene la [documentación reconciliada](project-status.md). No confundir
un build local o un hash correcto con aceptación del MVP o firma del editor.

## Preparación local

En un entorno de desarrollo con Python 3.11+, setuptools y wheel disponibles:

```bash
python tools/release_artifacts.py version
python -m unittest discover -s tests
python -c "from setuptools.build_meta import build_sdist, build_wheel; build_sdist('dist'); build_wheel('dist')"
python tools/release_artifacts.py checksums dist factoria-0.3.0-py3-none-any.whl factoria-0.3.0.tar.gz
python tools/release_artifacts.py verify dist
```

Construir en un checkout limpio del commit candidato; no mezclar artefactos viejos.
La herramienta solo procesa los nombres indicados, rechaza rutas, duplicados,
symlinks y archivos vacíos. Una suma incorrecta o archivo ausente devuelve código 1.
No descarga ni ejecuta contenido. `SHA256SUMS` debe obtenerse del mismo canal
verificado que la release: no identifica al firmante ni protege si se sustituye
tanto el archivo como su manifiesto.

Para repetir la comprobación de actualización Python con dos wheels locales de
confianza, el siguiente comando crea y elimina un venv y seis repositorios de
prueba. Instala solo esos archivos, sin acceder al índice de paquetes, y compara
los datos del proyecto y un HOME aislado tras actualizar y reabrir dos veces:

```bash
python tools/distribution_smoke.py /ruta/factoria-0.2.0-py3-none-any.whl dist/factoria-0.3.0-py3-none-any.whl --report /ruta/h06-smoke.json
```

Requiere Git, Python con venv/pip y el entorno de desarrollo de Factoria instalado.
No usa los datos del usuario ni arranca un proveedor. Una prueba con un wheel
anterior construido del checkout de desarrollo no equivale a usar una release
anterior publicada. El informe contiene hashes de ambos paquetes y sus límites.

## Windows (pendiente de ejecutar)

El workflow existente construye `Factoria.exe` y `Factoria-Setup-0.3.0.exe`,
comprueba versiones, instala, reinstala y reabre un proyecto de laboratorio con
agente/skill/workflow propios. Compara hashes del proyecto y desinstala.
Genera `SHA256SUMS` junto a los dos ejecutables. La reinstalación de la misma
versión no demuestra actualización desde una versión anterior.

Antes de publicar se necesita además un equipo Windows de pruebas:

1. Instalar el binario anterior verificado y preparar un proyecto con recursos propios.
2. Cerrar procesos, guardar copia de `%USERPROFILE%\.factoria` y del proyecto
   (incluidos `.factoria`, `AGENTS.md`, `.agents` y `.opencode`) fuera del directorio de instalación.
3. Registrar versión anterior, versión candidata, Windows/arquitectura y hashes.
4. Verificar el nuevo instalador, reinstalar en la misma carpeta y abrir dos veces.
5. Comparar los archivos propios con la copia, listar workflows y comprobar la
   integración. Si aparecen recursos generados desactualizados, previsualizar
   `project prepare` y revisar el diff antes de autorizar `--yes`.
6. Probar restauración usando el instalador anterior y la copia de datos. Registrar
   resultados, incidencias y evidencias. No borrar proyectos al desinstalar.

Para verificar una descarga en PowerShell sin Python:

```powershell
$name = 'Factoria-Setup-0.3.0.exe'
$expected = (Get-Content .\SHA256SUMS | Where-Object { $_.EndsWith("  $name") })
if (@($expected).Count -ne 1 -or $expected -notmatch '^[0-9a-f]{64}  ') { throw 'Manifiesto inválido' }
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $name).Hash.ToLowerInvariant()
if ($actual -ne $expected.Substring(0,64)) { throw 'SHA-256 incorrecto: no ejecutar' }
```

Los binarios no están firmados con Authenticode. No presentar SHA-256 como firma
digital ni aconsejar desactivar las protecciones de Windows.

## Publicación posterior

Tras cerrar las dependencias, revisar changelog y evidencias, validar CI y obtener
autorización para reactivar Actions. No reactivarlo para esta preparación.
Crear el tag `v0.3.0` sobre el commit verificado; el tag y ambos TOML deben coincidir.
Publicar una release con notas, commit, archivos finales y sus checksums; descargar
de nuevo y comparar sus bytes/hashes antes de declarar H06 completado. Este
documento es un procedimiento pendiente: no ha creado tag, release ni binarios Windows.

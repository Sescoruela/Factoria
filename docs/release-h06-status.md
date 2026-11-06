# H06 · Evidencia parcial — 06/11/2026

**En curso, sin tag ni release publicada.** Código preparado para 0.3.0.
GitHub Actions sigue deshabilitado por petición del usuario; no se ha reactivado,
no se ha ejecutado CI remoto ni construido un binario Windows en esta entrega.

## Comprobado localmente

- Linux, Python 3.12.14: 335 tests unittest correctos (incluye seis nuevos de release).
- Build wheel y sdist con setuptools; recursos HTML/JS, capabilities y release.toml
  presentes en wheel; herramientas, documentación e instalador fuente en sdist.
- Checksum offline de ambos paquetes: correcto. Tests negativos cubren corrupción,
  archivo ausente, manifiesto malformado, duplicados y traversal.
- Instalación real en venv aislado y actualización 0.2.0 → 0.3.0 mediante wheels
  locales, sin red ni proveedores. Dos reaperturas, workflow propio y conservación
  exacta de 37 archivos del proyecto/HOME. [Informe](release-h06-smoke.json).
- La versión anterior se construyó del checkout local previo a H06 (base de
  desarrollo 0.2.0), no de una release etiquetada publicada. El ensayo no prueba
  todas las instalaciones históricas ni la UI en un navegador.
- Update/rollback en proceso frozen devuelve instrucciones de reinstalación antes
  de crear el updater Python. El test confirma que no se intenta usar pip.
- Tres tests previos de argumentos Codex se hicieron independientes de la presencia
  del CLI en el host; los tests de descubrimiento permanecen separados. No se
  ejecuta ni autentica Codex en estos tests.

## Preparado, todavía no ejecutado

- Pipeline Windows: metadatos coherentes, inclusión de recursos, instalación,
  reinstalación de la misma versión, reapertura del proyecto configurado,
  comparación de hashes y generación/verificación de SHA256SUMS.
- Parseo local del YAML correcto; eso no acredita ejecución de PowerShell,
  PyInstaller ni Inno Setup en Windows.
- Procedimientos de descarga/integridad, actualización de checkout/Python/binario,
  copia de datos y retorno a una versión anterior en [release-process.md](release-process.md).

## Para cerrar H06

Cerrar la aceptación externa de H05 y la documentación H07. Cuando el usuario
autorice reactivar Actions, ejecutar y revisar CI multiplataforma e instalador.
Probar además actualización desde el binario anterior en un Windows de pruebas,
reapertura visual, conservación de configuración y recuperación desde copia.
Etiquetar/publicar el commit validado con notas, binarios y checksums; comprobar
la descarga final. Binarios sin Authenticode: no presentarlos como firmados.

H06 y sus criterios compuestos siguen abiertos hasta tener esas evidencias.

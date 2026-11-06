# Plantillas reutilizables entre proyectos (H08)

La plantilla JSON v1 contiene un nombre, skills del catálogo, agentes básicos y
propios y workflows basados en fix/feature. Exporta la configuración **guardada**,
no los borradores. No copia memoria, políticas ni comandos del proyecto de origen.

## Desde la aplicación

1. Seleccionar el origen y guardar o descartar sus borradores.
2. Abrir **Plantillas**, indicar nombre y pulsar **Exportar proyecto**.
3. Revisar el JSON y usar **Descargar JSON**. El detector bloquea secretos que
   reconoce; no garantiza detectar todos los datos privados. Revisar antes de compartir.
4. Seleccionar destino y abrir el JSON o conservarlo en el editor.
5. Pulsar **Ver cambios y conflictos**. Revisar proyecto, recursos nuevos,
   reutilizados y conflictos. Cualquier conflicto bloquea toda la importación.
6. Pulsar **Aplicar al proyecto seleccionado** y confirmar. Revisar el diff en Git
   y preparar ambas herramientas después. No se inician ni autentican proveedores.

Disponible en ambos shells. Cambiar proyecto, contenido o catálogos invalida el
preview. Abrir/exportar otra plantilla pide confirmación antes de sustituir contenido.

## Desde la terminal

```bash
factoria --project /ruta/origen project templates export --name "Equipo API" --output equipo-api.json
factoria --project /ruta/destino project templates import equipo-api.json
# Revisar create/reuse/conflicts y copiar token del preview:
factoria --project /ruta/destino project templates import equipo-api.json --yes --token "TOKEN_DEL_PREVIEW"
```

Sin `--output`, export muestra JSON por stdout. Con `--output`, crea un archivo
exclusivo y falla si existe. `--read-only` impide exportar a archivo e importar
con `--yes`; permite lectura/export por stdout y preview. Al escribir se vuelve
a comprobar la política vigente.

## Portabilidad y conflictos

| Incluido | Excluido |
| --- | --- |
| Skills gestionadas, metadatos y contenido exacto | Markdown ajeno y archivos arbitrarios |
| Instrucciones, roles, referencias y perfiles abstractos de agentes | Preferencias de máquina, rutas de ejecutables, configuración global y mapas de modelos |
| Workflows y preferencias portables por etapa | Credenciales, memoria, políticas, comandos, historial, snapshots y assets generados |

`codex`/`opencode` y los perfiles abstractos son preferencias del proyecto, no
modelos efectivos ni rutas de instalación. Las skills referenciadas deben estar
incluidas en el catálogo exportado. Una referencia como `docs/reglas.md` bloquea
la exportación: trasladar conscientemente el conocimiento al catálogo y reasignarlo.
No se copian archivos externos silenciosamente.

Los recursos idénticos se reutilizan; reimportar es idempotente. Un identificador
con contenido distinto o un archivo ajeno en la ruta de skill produce conflicto.
No hay sobrescritura forzada ni renombrado automático. Se conservan las otras
entradas del destino; el formato de los JSON puede normalizarse al combinarlos.
Los básicos implícitos pueden recibir configuración del origen si no se guardaron
explícitamente; un básico guardado distinto también produce conflicto.

Se rechazan versiones/campos desconocidos, duplicados, referencias incompletas,
roles incompatibles, orden inseguro, rutas externas, symlinks y secretos detectables.
Límite: 1 MiB. Las políticas, memoria y comandos del destino no cambian. Un workflow
importado puede seguir bloqueado por ellas. Los flujos activos mantienen su snapshot.

## Fallos y recuperación

Antes de escribir se guarda copia y `journal.json` en la ruta Git
`factoria/template-imports/<id>/` (normalmente `.git/factoria/template-imports/`).
No se comparte en la plantilla. Se usan temporales/reemplazo atómico por archivo
y creación exclusiva. Si falla una escritura se intenta restaurar lo escrito por
la importación, conservando cualquier edición externa posterior.

El conjunto de varios archivos **no es una transacción atómica frente a una caída**.
Si el journal queda `pending` o `failed`, detener ediciones, conservar los cambios
externos y revisar diff/originales del journal antes de restaurar solo esos recursos.
No reemplazar toda `.factoria`: contiene otros datos del proyecto. Si no se pudo
restaurar o hubo edición externa, el error señala la copia. Recuperación automática
tras caídas sigue en H13.

## Evidencia y límites

H08: **351 tests** locales en Linux/Python 3.12.14, incluidos 16 de plantillas.
Cubren equivalencia en repositorio nuevo, ambas integraciones, idempotencia,
conflictos, concurrencia, política, secretos/rutas, disco, snapshots, CLI y API
autenticada de ambos shells. Sintaxis JS y recurso empaquetado comprobados.

El navegador disponible devolvió conexión rechazada al laboratorio local; no se
afirma validación visual. Tampoco aceptación de proveedores, CI remoto o Windows
nuevos. Actions sigue deshabilitado. H06 permanece abierto: H08 entrega código de
reutilización sin publicar una release ni cerrar H05.

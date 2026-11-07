# Vista de relaciones del proyecto (H10)

**Relaciones** muestra la configuración guardada como tabla navegable:
**workflow → etapa configurable → agente → skills**. Funciona en ambos shells web
y como JSON de solo lectura con `factoria --project /ruta/proyecto project relations`.
No modifica el proyecto, no regenera integración ni inicia/autentica proveedores.

## Leer el mapa

- Se incluyen fix/feature implícitos cuando no hay configuración guardada, además
  de workflows y agentes propios. Cada etapa muestra su rol y las preferencias
  efectivas de perfil/plataforma: overrides de etapa primero, agente después.
- Las etapas desactivadas y workflows bloqueados por la configuración de flujos
  del proyecto se distinguen y no forman una ruta activa. El mapa no concede
  permisos de ejecución ni cambia el modelo o sandbox de la sesión externa.
- Verificaciones y aprobaciones obligatorias del tipo base siguen aplicándose;
  no se presentan como etapas configurables. No es un historial ni una snapshot
  de ejecución: los flujos iniciados conservan sus definiciones anteriores.
- Las skills Markdown ajenas al catálogo se muestran por ruta, sin su contenido
  y sin editor de catálogo. Las rutas equivalentes del proyecto se unifican.

## Diagnóstico

| Señal | Significado |
| --- | --- |
| Sin ruta activa | Agente/skill no alcanzable desde un workflow permitido y una etapa habilitada, con referencias válidas |
| No existe / no disponible | Referencia rota, archivada, insegura o con rol incompatible |
| Archivado / pendiente | ID reservado por H09; no se confunde con un recurso activo ni se restaura automáticamente |
| Integración vigente | `project check` no encuentra cambios ni conflictos |
| Integración desactualizada | Hay recursos generados que revisar/preparar; el mapa muestra cambios y conflictos |
| Integración no verificable | La configuración/memoria no permite comprobarla; no se afirma que esté vigente |

Un recurso sin ruta activa no es necesariamente prescindible: puede usarse fuera
de Factoria. No se archiva ni se elimina automáticamente. Los workflows son puntos
de entrada y no se clasifican como huérfanos.

Si hay catálogos ilegibles o entradas inválidas, se conserva un mapa parcial y un
diagnóstico. No se reemplaza una configuración rota por valores predeterminados
aparentemente correctos. Con información incompleta no se certifican huérfanos.
Un archivo de recursos ilegible tampoco se presenta como vacío.

## Abrir el editor sin perder borradores

Pulsar workflow/etapa abre ese workflow en el diseñador; pulsar agente o skill
gestionada abre su editor existente. Se comprueba de nuevo proyecto y revisión
guardada antes de cargar datos. Una referencia inexistente o no editable no tiene
un editor automático: corregir el diagnóstico o usar el archivo de recursos.

Si hay borradores o un guardado en curso, el salto se bloquea conservando los datos.
Guardar o descartar explícitamente en el editor correspondiente y volver al mapa.
Si aparece un borrador durante la petición asíncrona, también se conserva.
Actualizar el mapa sigue permitido: solo lee configuración guardada y no reemplaza
los borradores de los editores.

El shell clásico ya dispone del diseñador; para agentes/skills abre la interfaz
completa en `/editors`, en otra pestaña del mismo servidor con la autenticación
local existente. La pestaña original se conserva. Si el navegador bloquea la
apertura, se muestra un enlace. El destino comprueba el proyecto y carga el recurso
actual antes de editarlo. No hay escritura automática al seguir el enlace.

## Consistencia y límites

Las fuentes se leen con rutas del proyecto verificadas, sin seguir symlinks, y con
captura limitada: 2 MiB por archivo, 8 MiB acumulados y hasta 2048 entradas por
carpeta examinada. Las fuentes que exceden límites se diagnostican; no se ignoran
como si fueran configuración válida. Se contrastan revisiones antes/después para
avisar de cambios durante la lectura. Las instrucciones y contenido de skills no
forman parte del JSON del mapa, aunque sus cambios invalidan la revisión.

La API `/api/project/relations` exige el token local y que el proyecto coincida
con el seleccionado; no acepta rutas arbitrarias para leer otro proyecto. En CLI,
`--read-only` permite esta consulta. El código de salida es 1 para errores o lectura
inconsistente; los huérfanos e integración desactualizada por sí solos no son errores
de estructura. Para comprobar readiness de integración usar `project check`.

## Evidencia — 07/11/2026

382 tests completos correctos en Linux/Python 3.12.14, incluidos 14 de H10:
cadenas reales, herencia/overrides, rutas normalizadas/externas, referencias
inexistentes e incompatibles, huérfanos, etapas/políticas, archivos archivados,
fuentes corruptas/grandes/symlinks, cambios durante lectura, privacidad del payload,
CLI y API autenticada de ambos shells. Se comprueba además el puente `/editors`
y guardado real mediante los endpoints existentes de agentes y skills.

`node tests/ui/relations_controller_smoke.cjs` prueba el controlador con DOM/API
simulados: editores, borradores y carreras asíncronas, fuente/proyecto obsoletos,
etiquetas literales y puente/enlace del shell clásico. Los smokes H08/H09 siguen
pasando. Sintaxis JS, enlaces y recursos empaquetados comprobados.
No se afirma validación visual en navegador, CI remoto, Windows ni aceptación de
proveedores nuevos. Actions sigue deshabilitado; H05/H06 permanecen abiertos.

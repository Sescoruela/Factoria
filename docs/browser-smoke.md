# Pruebas de navegador (H11)

H11 está implementado y validado localmente. **Sigue abierto hasta ejecutar y
revisar la evidencia de CI**: Actions permanece deshabilitado por petición del
usuario. Añadir el workflow no lo reactiva. H05/H06 y la aceptación conjunta #2
también siguen pendientes.

## Ejecución reproducible

Desde la raíz del repositorio, con Python 3.11+ y Node 24:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e .
npm ci --prefix tests/ui/browser --ignore-scripts --no-audit --no-fund
cd tests/ui/browser
npx playwright install --with-deps chromium --only-shell
cd ../../..
FACTORIA_TEST_PYTHON="$PWD/.venv/bin/python" npm --prefix tests/ui/browser test
```

En Windows, indicar el intérprete `.venv\Scripts\python.exe` mediante
`FACTORIA_TEST_PYTHON` en PowerShell antes de ejecutar npm. Esta entrega no acredita
una ejecución Windows. Playwright está fijado con lockfile en el paquete de
desarrollo; Python conserva `dependencies = []`. No se necesita Node ni Playwright
para utilizar Factoria o ejecutar los tests unittest existentes.

La configuración usa un solo worker, sin reintentos, contra dos servidores locales
reales. El fixture aísla HOME, preferencias y repositorios Git en una carpeta temporal;
no prepara proveedores, no ejecuta LLM ni toca los proyectos del usuario. Sus rutas
`/__test__/fixture` y `/__test__/reset` existen exclusivamente en el script de pruebas,
no en la aplicación distribuida. No reutiliza servidores que ya estén escuchando.
`FACTORIA_BROWSER_PORT` cambia el puerto inicial (8769; clásico en el siguiente).

## Cobertura

22 casos con Chromium real, formularios y HTTP reales:

| Recorrido | Comprobación |
| --- | --- |
| Crear/editar/reabrir | Skill → agente → workflow, contenido exacto y referencias persistidas, recarga real del navegador |
| Interfaz principal y clásica | Editores completos en `/` y `/editors` del servidor clásico; diseñador clásico en su raíz |
| Borradores | Actualizar, cancelar salida/cambio de proyecto y descartar explícitamente |
| Dos pestañas | Revisiones reales; el segundo guardado devuelve 409 y conserva el borrador y la versión ya guardada |
| Proyecto cambiado externamente | Actualizar la primera pestaña mantiene el borrador original; guardar no escribe en ninguno de los dos proyectos |
| Guardado fallido | Respuesta 503 inyectada en el navegador; mantiene formulario/archivo y permite reintentar contra la API real |
| Autenticación | Reapertura autenticada y rechazo 403 sin token en ambos servidores |

Los tests registran errores JavaScript de página. No sustituyen la revisión visual,
accesibilidad, otros navegadores, Windows, fallos reales de disco, snapshots nativas
ni aceptación autenticada de Codex/OpenCode. Los fallos de persistencia de disco
siguen cubiertos por unittest; el 503 comprueba el comportamiento del formulario.

## Informes y fallo de control

Por defecto se escriben dentro de `tests/ui/browser/`, ignorados por Git:

- `playwright-report/index.html`: informe navegable.
- `results.json` y `results.xml`: resultados estructurados y JUnit.
- `test-results/`: captura, contexto del error y traza por fallo con navegador iniciado.

Un fallo antes de iniciar el navegador puede generar solo el informe y el log de
arranque. El workflow sube la evidencia disponible también tras errores, durante
siete días. No usa secretos del repositorio ni `pull_request_target`.

Para comprobar la generación de evidencia de forma deliberada:

```bash
FACTORIA_BROWSER_PROBE_FAILURE=1 \
FACTORIA_BROWSER_ARTIFACT_DIR=/tmp/factoria-browser-probe \
FACTORIA_TEST_PYTHON="$PWD/.venv/bin/python" \
npm --prefix tests/ui/browser test -- --grep 'intentional artifact probe'
```

Este comando **debe fallar**; no pertenece a la suite normal. Inspeccionar captura,
traza e informes, después ejecutar la suite normal. `FACTORIA_BROWSER_ARTIFACT_DIR`
separa esa evidencia del resultado positivo. Para ver una traza, usar
`npx playwright show-trace <ruta/trace.zip>` desde `tests/ui/browser`.

## Evidencia local — 07/11/2026

22/22 correctos, sin saltos ni reintentos; 382 unittest correctos y los tres smokes
DOM/API históricos (skills, agentes en workflow y workflows propios). También se
ejecutó el fallo de control y se comprobaron captura PNG, traza ZIP e informes
HTML/JSON/JUnit. Resumen con hashes de las fuentes verificadas en
[h11-local-evidence.json](acceptance/h11-local-evidence.json).

Entorno: Linux, Python 3.12.14, Node 24.22.1, Playwright 1.62.1. El navegador normal
del entorno no podía iniciar por la restricción de sockets Unix y su descarga
estándar falló. Se ejecutó Chromium headless 153.0.8010.0, distribuido por
`@sparticuz/chromium` 153.0.0 instalado solo en una carpeta temporal, mediante
`FACTORIA_CHROMIUM_EXECUTABLE`. No es dependencia del repositorio. CI instala el
Chromium correspondiente al Playwright fijado: su ejecución aún no está acreditada.

Las pruebas detectaron y verificaron tres correcciones: respuestas completas de
estado tras guardar workflows/otras operaciones compartidas, autenticación local
conservada en `sessionStorage` al recargar la pestaña (token retirado de la URL), y
borradores de agente conservados si otra pestaña cambia el proyecto y se actualiza
la vista. El origen del borrador se valida antes de guardar.

Referencias de configuración: [CI](https://playwright.dev/docs/ci-intro),
[reporters](https://playwright.dev/docs/test-reporters) y
[configuración](https://playwright.dev/docs/test-configuration) de Playwright.

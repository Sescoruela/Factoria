# Manual de uso de Factoría

Factoría guarda la configuración de trabajo por repositorio. Codex u OpenCode
realizan el trabajo en su sesión y el CLI de Factoría registra la etapa, la
evidencia, las aprobaciones y las comprobaciones.

## 1. Preparar el entorno

Instala Factoría desde el código fuente siguiendo el [README](../README.md).
Para actualizar una copia, trae los cambios de Git y vuelve a instalarla en
el entorno que usas. Confirma que `factoria --version` funciona también en la
terminal de la sesión del agente. Un entorno virtual activado en una terminal
puede requerir activación en otra.

Abre la interfaz con `factoria ui`. Inicia sesión en Codex u OpenCode desde
la herramienta correspondiente. En **Plataformas**, Factoría muestra la
detección local del CLI y los indicios de ChatGPT Desktop por separado.
Comprueba en la sesión del agente que tiene acceso al repositorio, a Git
y al CLI de Factoría.

## 2. Probar con un repositorio desechable

Desde el checkout de Factoría, crea el laboratorio en una ruta nueva fuera de
otro repositorio.

```text
python tools/acceptance_lab.py prepare ../factoria-lab
```

El laboratorio crea repositorios independientes, con archivos de ejemplo,
configuración, ramas de trabajo y comprobaciones de referencia.

| Herramienta | Caso de corrección | Caso de funcionalidad |
| --- | --- | --- |
| Codex CLI | `factoria-lab/codex-cli/fix` | `factoria-lab/codex-cli/feature` |
| OpenCode | `factoria-lab/opencode/fix` | `factoria-lab/opencode/feature` |
| Codex en ChatGPT con checkout | `factoria-lab/chatgpt-checkout/fix` | `factoria-lab/chatgpt-checkout/feature` |

Abre la carpeta del caso en tu herramienta. Desde esa carpeta puedes consultar
la integración y los workflows disponibles.

```text
factoria project check
factoria project workflows
git status --short --branch
```

### Corrección

Pide «Usa fix-lab para corregir sum_even. Para [1, 2, 3, 4] debe devolver 6.
Conserva el comportamiento con vacíos, negativos y cero y las pruebas base».
También puedes seleccionar `$factoria-fix-lab` en Codex o
`/factoria-fix-lab` en OpenCode.

Comprueba que reproduce el fallo, corrige el predicado y ejecuta las pruebas
confirmadas. Revisa la evidencia y autoriza el commit local si el resultado
te convence.

### Funcionalidad

En el caso `feature`, pide «Usa feature-lab para añadir count_even(numbers)
sin cambiar sum_even. Cuenta el cero y los negativos pares. Una lista vacía
devuelve 0».

El flujo te presenta el plan antes de implementar. Revísalo y apruébalo cuando
estés de acuerdo. Después de las comprobaciones y la revisión, decide si
apruebas el resultado y autorizas el commit. El agente puede cerrar el flujo
con `factoria native finish <id>` tras el commit y con el árbol limpio.

## 3. Configurar un proyecto propio

1. En **Proyectos**, selecciona el repositorio e inicializa su memoria si hace
   falta. Registra los comandos de prueba que conozcas y hayas comprobado.
2. En **Skills**, crea una skill o guarda una desde **Plantilla de skill**.
3. En **Agentes**, crea un agente o elige una plantilla. Añade las skills que
   necesite y guarda.
4. En el diseñador de workflows, selecciona `fix` o `feature`. Asigna un agente
   compatible a cada etapa que quieras personalizar. Para una variante, crea
   un workflow a partir del tipo base y asígnale un identificador propio.
5. En **Integración**, revisa la vista previa y pulsa **Preparar ambas herramientas**.
   Revisa el diff y guarda en Git la configuración y los archivos generados.
6. Abre una sesión con acceso al proyecto y usa una rama de trabajo limpia.
   Pide la corrección o funcionalidad. Si tienes varias variantes, indica el
   identificador explícitamente.

La misma preparación está disponible en la terminal del proyecto.

```text
factoria project prepare
factoria project prepare --yes
factoria project check
```

| Si necesitas | Configuración |
| --- | --- |
| Definir el recorrido y sus estados | Diseñador de producto en `plan` con Flujos y estados |
| Definir y revisar una interfaz | Diseñador visual en `plan` y Revisor visual en `review` |
| Migrar un frontend a un backend nuevo | Contratos e integraciones en `plan` con Migración de APIs |
| Investigar un timeout o una incidencia | Diagnóstico SQL y rendimiento o Diagnóstico de producción en el agente de la etapa correspondiente |
| Comprobar recorridos y reglas | Revisión de usabilidad y Casos límite según la etapa |

Economía de contexto se incorpora al preparar la integración. Las guías indican
consultar el contexto relevante y usar `native --compact`. La salida compacta
conserva los datos del flujo. El consumo real depende de la sesión.

## 4. Seguir el flujo

La sesión ejecuta `factoria native` y recibe la etapa y el archivo de evidencia.
Cuando el workflow lo requiere, pide aprobación del plan, del resultado y del
commit en sus respectivos puntos. Si hay comprobaciones confirmadas, Factoría
las ejecuta durante la verificación. Si faltan, sigue la vía manual indicada.

Puedes consultar el estado desde el proyecto.

```text
factoria native status <id>
factoria history
```

| Situación | Qué comprobar |
| --- | --- |
| La sesión no encuentra `factoria` | Verifica el PATH en esa sesión y activa el entorno donde instalaste el paquete. |
| `project check` indica cambios o conflictos | Ejecuta la vista previa. Si hay ediciones manuales en archivos gestionados, revisa el diff antes de resolverlas. |
| El flujo se detiene por Git | Comprueba la rama, el árbol de trabajo y si hay un flujo activo. |
| La verificación falla | Abre la evidencia, corrige la causa y repite la verificación con el recorrido indicado por Factoría. |
| La sesión solo puede leer el proyecto | Comprueba el entorno y los permisos de la herramienta antes de iniciar un flujo que requiera editar. |

En una conversación de ChatGPT sin checkout, puedes adjuntar
`.factoria/generated/chatgpt-context.md` y el código que quieras comentar para
trabajar en modo propuesta. Las operaciones sobre el repositorio requieren
una sesión con acceso al proyecto y al CLI.

## 5. Compartir el resultado de la prueba

Para que se pueda reproducir tu observación, incluye estos datos en la incidencia.

```text
Sistema operativo y versión de Factoría
Codex u OpenCode y versión si está disponible
Caso de laboratorio, workflow o pantalla
Pasos para reproducirlo
Qué esperaba
Qué ocurrió y en qué etapa
Mensaje de error o captura revisada
```

Si la prueba salió bien, también interesa saber qué parte fue fácil de entender
y dónde tuviste que volver al manual. [Issues](https://github.com/Sescoruela/Factoria/issues)

Consulta el [protocolo de pruebas externas](acceptance/h05-protocol.md) si
quieres probar también flujos bloqueados, errores de verificación y sesiones nuevas.

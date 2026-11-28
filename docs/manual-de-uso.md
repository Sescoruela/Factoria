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

1. En **Inicio**, si todavía no has seleccionado un proyecto, consulta
   **Revisar integración** para ver qué instalaciones de Codex y OpenCode
   detecta Factoría. Pulsa **Elegir proyecto** y abre el repositorio. Si es la
   primera vez, pulsa **Revisar preparación inicial** y luego
   **Preparar memoria, agentes y skills**. En el mismo paso se generan los
   subagentes nativos de OpenCode, las skills y los comandos del proyecto.
2. Si ya hay memoria, en **Preparar proyecto** puedes revisar y regenerar la
   integración. Si
   Factoría muestra un conflicto, revisa los archivos indicados y vuelve a
   comprobar el proyecto. La preparación instala exclusiones en
   `.git/info/exclude` para que la configuración, la memoria generada y los
   archivos de Codex/OpenCode se queden en tu copia. Cada colaborador puede
   preparar su propio clon con sus agentes, flujos e historial.
   Si Factoría indica que algún archivo de configuración ya está versionado,
   coordina con el equipo su retirada del índice de Git para conservarlo en disco.
3. Elige **Corregir un problema** o **Añadir una funcionalidad**. Describe la
   tarea, elige Codex u OpenCode y copia la petición. Abre la herramienta
   elegida en el repositorio y pega la petición en tu rama de trabajo.

### Usar tus propios agentes y skills

Después de crear o editar un agente o una skill, abre **Integración → Ver
cambios** y prepara ambas herramientas. Factoría genera los archivos nativos
en esta copia local aunque todavía no hayas asignado el recurso a un workflow.
Consulta los nombres invocables en `.factoria/generated/agents.md` y
`.factoria/generated/skills.md`.

### Completar la memoria con OpenCode o Codex

Una vez preparada la integración, abre en **Inicio** el menú **Analizar memoria
con OpenCode o Codex**. Elige el CLI que hayas configurado, pulsa **Generar
memoria** y revisa las fuentes antes de **Guardar revisión**. El modelo de esa
herramienta recibe una selección de archivos versionados del repositorio como
contexto de solo lectura. Conviene iniciar sesión en la herramienta con antelación.

Si trabajas desde una sesión externa, pulsa **Copiar encargo de análisis**,
pega allí el encargo y vuelve con el JSON. En **Importar o editar informe JSON**, pega el resultado y pulsa **Revisar informe**.

La revisión cubre propósito, arquitectura, flujos, contratos, decisiones y
verificación. Los hallazgos citan archivos y tienen una sección para dudas
pendientes. Factoría guarda el resultado en `docs/memoria/revision.md` como
parte de la memoria local. Si quieres encontrarlo con el grafo, pulsa
**Generar índice**. Vuelve a preparar la integración para incorporarlo al
contexto portable.

El menú lateral agrupa las opciones que usarás después de preparar el proyecto.

| Menú | Qué puedes encontrar |
| --- | --- |
| **Trabajo** | Ejecuciones e historial |
| **Configurar proyecto** | Preparación para Codex y OpenCode, workflows, agentes, skills, relaciones, plantillas y archivo de recursos |
| **Herramientas** | Configuración de Codex y OpenCode, copias y recuperación, seguridad y consola |

Para actualizar el grafo, abre **Analizar memoria con OpenCode o Codex** en
**Inicio**, despliega **Grafo de memoria** y pulsa **Generar índice**.

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

Si quieres recuperar contexto entre sesiones, genera el [grafo de memoria](memory-graph.md)
con `factoria project memory-graph build`. Puedes consultar decisiones y módulos
relacionados con `factoria project memory-graph recall "tema"`.

### Consultar la memoria del proyecto

En el menú lateral, abre **Memoria del proyecto**. Usa el selector para leer
la memoria general, arquitectura, flujos, decisiones, verificación o la última
revisión disponible. Escribe un tema en **Buscar en los documentos** y pulsa
un resultado para saltar a su sección. Si cambias los archivos fuera de
Factoría, pulsa **Actualizar memoria**.

### Compartir agentes y skills

En **Agentes** o **Skills**, abre **Importar y exportar**. Elige el tipo de
recurso y pega el enlace de GitHub al archivo público. Puedes abrir un Markdown
local o importar un agente de Codex en TOML. Para los agentes, elige también la
función que tendrán en Factoría.

Revisa las instrucciones y la lista de cambios, pulsa **Añadir al proyecto** y
confirma. Si hay un conflicto, cambia el identificador o revisa el recurso
existente. Vuelve a preparar la integración para que Codex y OpenCode reciban
la configuración nueva.

Para compartir, elige **Skills**, **Agentes y skills** o **Proyecto completo**.
Pulsa **Preparar exportación**, revisa el JSON y descárgalo. Otra persona puede
abrir ese JSON desde **Revisar plantilla**.

### Diseñar un workflow

Abre **Configurar proyecto → Workflows** en la vista principal. Arrastra las cajas
en cualquier dirección y el fondo del lienzo para desplazarte. Usa los controles
de zoom o **Ajustar vista** para encuadrar el diagrama.

Para dibujar una rama, pulsa el puerto de salida de una caja y luego la entrada
de otra. Repite desde la misma salida para abrir otra rama, o hacia la misma
entrada para reunir varias. Puedes añadir cajas de análisis con nombre y quitar
conexiones desde el selector. Pulsa **Guardar** para conservar el diagrama en el
proyecto.

Al iniciar Fix, Feature o un workflow con nombre desde Codex u OpenCode, la
ejecución sigue la ruta guardada. Una caja de análisis pide al agente explorador
que documente sus hallazgos sin editar código. Si dos ramas llegan a la misma
caja, ambas deben terminar antes de continuar. Las ramas se ejecutan una a una.
El guardado valida que el grafo tenga una entrada en explore, esté conectado
y conserve el orden de las etapas obligatorias.

Por ejemplo, crea un workflow con identificador `fix-qa` y nombre **fixQA**.
Conecta las ramas de revisión de contrato y datos a una caja de QA. Guarda y
vuelve a preparar la integración. Inícialo con `$factoria-fix-qa` en Codex o
`/factoria-fix-qa` en OpenCode. Se usa el grafo de **fixQA**. El comando del Fix
base sigue seleccionando su propio workflow.

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

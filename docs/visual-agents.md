# Especialistas visuales

Las plantillas **Diseñador visual** y **Revisor visual** se copian como agentes
normales editables en cada proyecto. No se añaden automáticamente ni cambian flujos
existentes. No incorporan dependencias de runtime ni un proveedor de imágenes.

## Uso

1. Seleccionar el proyecto y abrir **Agentes**.
2. En **Especialista visual**, elegir **Diseñador visual** y **Crear desde plantilla**.
   Revisar las instrucciones y pulsar **Guardar agente**.
3. Repetir con **Revisor visual** para una revisión visual explícita.
4. En el diseñador del workflow, asignar `visual-designer` a **plan / planner** y
   `visual-reviewer` a **review / reviewer**. Guardar el workflow. Para un fix que
   necesite planificación visual, activar primero su etapa plan.
5. En **Integración**, revisar los cambios y preparar ambas herramientas. Revisar
   y guardar los archivos generados en Git antes de iniciar el próximo flujo.

Crear desde plantilla abre un borrador; no guarda ni asigna el agente. Si el ID
ya existe, no se sobrescribe: modificar el existente o crear uno con otro ID.
Los flujos iniciados conservan su snapshot y no adquieren los especialistas nuevos.

## Trabajo esperado

El diseñador conserva las responsabilidades técnicas del planner y añade la
sección «Diseño visual» a `plan.md`, antes de la aprobación: intención, jerarquía,
tipografía y colores concretos, espaciado, componentes, estados, adaptación a
tamaños y criterios observables. Respeta la identidad existente y justifica los
cambios. Las decisiones forman parte del mismo plan que recibe el implementador.

El revisor mantiene la revisión técnica y el contrato JSON, y contrasta el resultado
con el plan aprobado. Examina aplicación y capturas reales si dispone de herramientas,
indicando pantallas, tamaños y estados comprobados y lo pendiente. No presenta
pruebas unitarias como evidencia visual ni bloquea por preferencias personales.
En tareas sin interfaz ambos conservan las responsabilidades técnicas del rol base.

En un organizador de turnos, por ejemplo, la dirección visual debe priorizar lectura
de horas y empleados, cobertura y conflictos, edición táctil y densidad adecuada al
móvil. No impone tarjetas, gradientes, una paleta o una tecnología por defecto.

## Límites y evidencia local (08/11/2026)

Las plantillas son instrucciones, no procesos o modelos independientes garantizados.
En modo directo la sesión anfitriona realiza las etapas. Inspeccionar APK, emulador,
navegador o capturas depende de sus herramientas y permisos. Sin inspección real,
la aceptación visual queda pendiente; no se garantiza calidad estética por configurar
un agente ni se declara cerrado H05.

Validación: pruebas Python de lectura sin escritura, guardado/asignación/exportación
a ambas herramientas, incompatibilidad de roles y no sobrescritura. Smoke DOM/API
`tests/ui/visual_agents_smoke.cjs` (requiere jsdom solo como herramienta de desarrollo):
borrador sin escritura, cancelación conservadora, guardado, duplicados y selector
compatible. No equivale a aceptación de LLM, APK ni navegador real. Actions sigue
deshabilitado.

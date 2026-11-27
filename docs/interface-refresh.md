# Interfaz de trabajo — 07/11/2026

Desde el 24/11/2026, ambas vistas comparten una barra azul noche, un monograma
menta y acciones en índigo. Inicio abre con el proyecto activo y su siguiente tarea.
En escritorio, los demás proyectos preparados se pueden seleccionar a su lado.
**Memoria del proyecto** tiene acceso directo al análisis y al grafo. El formulario
para importar JSON se despliega cuando se necesita.

Actualización del menú del 19/11/2026. **Inicio** y **Proyectos** tienen acceso
directo. **Trabajo**, **Configurar proyecto** y **Herramientas** se despliegan al
abrirlos. Al entrar por un enlace directo se abre el grupo de la sección. En
móvil, el menú admite teclado y Escape devuelve el foco al botón **Menú**.

## Cambios de uso

- **Inicio** muestra el siguiente paso del proyecto y un acceso a su configuración.
  Los accesos abren el workflow o panel correspondiente; los catálogos con errores
  se presentan como pendientes de revisión, no como catálogos vacíos correctos.
- **Agentes y skills** separan lista y formulario en escritorio, señalan la selección
  y explican el estado inicial sin llenar el área de tarjetas repetidas. En móvil
  se apilan conservando el formulario y sus borradores.
- **Workflows** mantiene visible la creación y recoge nombre/descripción en un
  desplegable: los básicos lo dejan cerrado; al crear o abrir uno propio se abre.
  Se reduce el espacio vacío del lienzo y las conexiones se calculan con la altura
  visible de los nodos, para llegar a sus puertos tras el cambio tipográfico.
- **Móvil** dispone de menú plegable con estado expandido, foco de teclado al
  contenido, enlace para saltar la navegación y etiquetas de campos. El scroll
  horizontal del diagrama queda dentro del lienzo.
- Los accesos del servidor clásico reutilizan `/editors` cuando requieren el editor
  completo, con autenticación existente y comprobación de borradores. Limpiar el
  token de la URL conserva ahora el fragmento de destino de esos enlaces.

Los cambios viven en `web/frontend/interface.css` y `web/frontend/interface.js`, compartidos por ambas
vistas. Se mantienen las políticas, revisiones, confirmaciones y guardados existentes.
No se añaden librerías de runtime, fuentes externas ni arranque de proveedores.

## Capturas de la versión del 07/11/2026

Proyecto de demostración creado en el fixture desechable, con una skill, un agente
propio y un workflow propio. Las rutas temporales visibles no son datos del usuario.

![Resumen en escritorio](images/interface/overview.png)

![Lista y formulario de agentes](images/interface/agents.png)

![Editor de workflows](images/interface/workflows.png)

[Vista móvil](images/interface/mobile.png)

## Comprobaciones y límites

406 unittest correctos y 31/31 casos Chromium reales locales. Los seis casos nuevos
comprueban datos/accesos del resumen, teclado/menú móvil, ancho del viewport y
scroll del lienzo, selección inicial de proyecto, puente clásico y conexiones de
los nodos. Se conservan los recorridos de crear/editar/reabrir, borradores,
conflictos entre pestañas, fallos de guardado y recuperación H13.

Inspección visual de Resumen, Agentes, Workflow, vista clásica y móvil; viewports
1440×1000 y 390×844, con capturas de documento completo. El documento móvil no desborda su viewport de 390 px. Esto no
certifica accesibilidad WCAG completa, todos los tamaños, Firefox/Safari o Windows.
Los controles específicos de teclado y etiquetas están comprobados, no sustituyen
una auditoría completa con tecnologías de asistencia.

CSS/JS, wheel y controladores DOM/API comprobados. Evidencia con hashes:
[interface-local-evidence.json](acceptance/interface-local-evidence.json).
Actions permanece deshabilitado: sin CI remoto ni nueva aceptación de proveedores.
H05/H06/H11 siguen abiertos y no se publica una release.

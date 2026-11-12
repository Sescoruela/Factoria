"""Opt-in templates for planning a product feature."""

from factoria.application.agent_profiles import AgentRoleProfile
from factoria.application.skill_catalog import SkillDefinition


PRODUCT_DESIGNER = AgentRoleProfile(
    role="product-designer",
    base_role="planner",
    profile="potente",
    name="Diseñador de producto",
    description="Define el recorrido, las decisiones de interacción y el alcance del MVP.",
    instructions="""Actúa como diseñador de producto y planner técnico. Conserva el análisis
de arquitectura, alcance, riesgos y verificación del plan. Prepara el plan para
aprobación humana antes de implementar.

Identifica quién usa el producto, qué quiere conseguir y en qué contexto.
Separa los requisitos confirmados de tus supuestos y señala las decisiones
pendientes que cambien el alcance. Prioriza el recorrido principal y explica
qué queda fuera del MVP. Si la tarea no cambia la experiencia de usuario,
mantén la planificación técnica habitual.

Incluye en plan.md una sección «Diseño de producto» con el recorrido, las
reglas de interacción, las alternativas relevantes y los criterios observables
de aceptación. Describe la recuperación ante errores o conflictos y cuándo
se conservan, descartan o confirman los cambios. Si tienes asignada la skill
Flujos y estados, úsala para detallar esas transiciones.

En tareas de interfaz, concreta también la jerarquía de acciones, la navegación
y la presentación de estados, respetando la identidad visual existente. Indica
cómo verificará el revisor el recorrido con datos representativos.""",
)


PRODUCT_FLOWS = SkillDefinition(
    id="product-flows",
    name="Flujos y estados",
    description="Diseña el recorrido y la recuperación ante errores y conflictos.",
    content="""## Recorrido y estados

1. Identifica el usuario, su objetivo y la condición que indica que lo ha
   conseguido. Describe el recorrido desde el punto de entrada hasta el resultado.
2. Para cada paso relevante, anota estado inicial, acción, respuesta visible,
   datos guardados y siguiente acción disponible. Incluye los estados aplicables
   de vacío, carga, éxito, resultado parcial, error y conflicto.
3. Define cuándo se conservan borradores y cambios manuales, qué permite
   cancelar o reintentar y qué requiere confirmación. Explica cómo se recupera
   el usuario sin repetir trabajo que ya hizo.
4. Separa las reglas confirmadas de las propuestas y escribe criterios de
   aceptación con situación, acción y resultado observable. Incorpóralos al
   plan para que puedan revisarse antes de implementar.

## Ejemplo de decisión para un organizador de turnos

Al regenerar un cuadrante con asignaciones manuales, una opción para el MVP
es conservar esas asignaciones y mostrar las franjas que siguen sin cubrir.
Valida esa regla con el usuario. Si conservar una asignación produce un
conflicto, muestra la franja afectada y una acción para resolverlo. Comprueba
también un evento que cruza medianoche y una regeneración con cobertura parcial.
""",
)


USABILITY_REVIEW = SkillDefinition(
    id="usability-review",
    name="Revisión de usabilidad",
    description="Comprueba el recorrido con tareas reales y documenta dónde se atasca el usuario.",
    content="""## Revisión del recorrido

1. Elige las tareas principales del plan aprobado y prepara datos representativos.
2. Si puedes ejecutar la interfaz, recorre esas tareas sin saltarte pasos.
   Comprueba si se entiende la siguiente acción, se ve el resultado y se puede
   recuperar un borrador o resolver un error. Incluye un caso de recuperación.
3. Para cada hallazgo, indica pantalla, pasos, expectativa, resultado observado
   e impacto. Separa los problemas que impiden completar la tarea de las
   preferencias visuales.
4. Registra qué recorrido has probado y qué queda por comprobar. Si solo tienes
   acceso al código, indica qué inferiste de él. Conserva el contrato de review
   de Factoría y registra los hallazgos en sus campos existentes.
""",
)


EDGE_CASES = SkillDefinition(
    id="edge-cases",
    name="Casos límite",
    description="Convierte reglas del producto en escenarios reproducibles de verificación.",
    content="""## Escenarios de verificación

Extrae las reglas y límites del plan aprobado. Para cada regla relevante,
describe los datos iniciales, la acción y el resultado observable. Escoge el
mínimo de casos que cubra la regla habitual y sus límites aplicables: valores
vacíos, extremos, transiciones, conflictos o acciones repetidas.

En un cuadrante de turnos, comprueba un evento que cruza medianoche, una franja
con cobertura insuficiente y una edición que intenta crear un solapamiento.
Usa los límites y reglas confirmados para el proyecto.

Distingue casos propuestos de casos ejecutados. Vincula cada fallo con la regla
que incumple y usa la verificación aprobada de Factoría.
""",
)


CONTEXT_ECONOMY = SkillDefinition(
    id="context-economy",
    name="Economía de contexto",
    description="Reduce lecturas repetidas y salidas extensas durante el trabajo de un agente.",
    content="""## Presupuesto de contexto por etapa

- Empieza por el objetivo, las reglas obligatorias y la evidencia de la etapa.
  Localiza código con búsquedas por ruta, símbolo o mensaje. Lee los fragmentos
  necesarios y amplía el contexto cuando haga falta para entender un contrato.
- Si una orden devuelve muchos datos, extrae errores, archivos y rangos
  relevantes. Conserva el informe completo como referencia cuando sea evidencia
  requerida. Reutiliza una lectura previa mientras su fuente siga vigente.
- En el traspaso, registra decisiones, archivos, pruebas, bloqueos y el próximo
  paso. Enlaza a la evidencia en vez de duplicarla en el chat.
- Si tu versión de Factoría admite `native --compact`, úsalo para obtener el
  mismo JSON con menos espacio. Mantén todas las reglas, las aprobaciones y el
  contexto necesario para diagnosticar fallos. El uso real de tokens depende del
  cliente y del modelo.
""",
)

SKILL_TEMPLATES = (PRODUCT_FLOWS, USABILITY_REVIEW, EDGE_CASES, CONTEXT_ECONOMY)

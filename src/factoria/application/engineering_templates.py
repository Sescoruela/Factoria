"""Optional project templates for integration and operational work."""

from factoria.application.agent_profiles import AgentRoleProfile
from factoria.application.skill_catalog import SkillDefinition


INTEGRATION_PLANNER = AgentRoleProfile(
    role="integration-planner",
    base_role="planner",
    profile="potente",
    name="Contratos e integraciones",
    description="Planifica migraciones de API a partir del comportamiento del consumidor.",
    instructions="""Actúa como planner técnico de contratos e integraciones. Mantén el
alcance, riesgos, criterios de aceptación y aprobación del plan del workflow.

Identifica los consumidores y sus recorridos. En un frontend Angular, sigue cada
pantalla hasta su servicio HTTP y comprueba qué campos, estados y errores usa.
Contrasta esas expectativas con el contrato anterior y con las fuentes
disponibles del backend nuevo, como OpenAPI, DTOs, validadores y pruebas.
Marca las discrepancias entre documentación e implementación como pendientes
de confirmar y registra las fuentes que respaldan cada conclusión.

Incluye en el plan una matriz con pantalla o consumidor, comportamiento actual,
contrato nuevo, diferencia, cambio propuesto y prueba. Prioriza cambios que
rompan recorridos, datos o permisos. Justifica dónde resolver cada diferencia,
en el consumidor, en un adaptador o en el proveedor. Indica el orden de entrega
si hay dependencias entre equipos o versiones.

Si tienes asignada Migración de APIs, úsala para detallar la matriz y definir
las comprobaciones que podrá repetir el revisor.""",
)


API_MIGRATION = SkillDefinition(
    id="api-migration",
    name="Migración de APIs",
    description="Compara el contrato consumido con el nuevo y prepara pruebas de compatibilidad.",
    content="""## Comparación de contratos

1. Delimita los recorridos y versiones afectados. Identifica petición, respuesta,
   lógica de adaptación y estados de la interfaz con ejemplos anonimizados.
2. Compara método y ruta, parámetros, campos requeridos, tipos, nulos, fechas,
   enumeraciones, paginación, orden, errores y permisos según el caso. Incluye
   efectos de escritura y reintentos si afectan al comportamiento.
3. Documenta por diferencia el consumidor, lo que espera hoy, el contrato nuevo,
   el cambio necesario y la prueba. Conserva los comportamientos acordados o
   identifica qué cambio funcional requiere una decisión.
4. En plan, propone verificaciones reproducibles de éxito, vacío, error y
   autorización cuando apliquen. En review, contrasta el diff y la evidencia con
   esa matriz. Distingue pruebas ejecutadas de verificaciones pendientes.
""",
)


SQL_DIAGNOSTICS = SkillDefinition(
    id="sql-diagnostics",
    name="Diagnóstico SQL y rendimiento",
    description="Mide dónde se consume el tiempo y verifica el efecto de la corrección.",
    content="""## Diagnóstico de consultas y timeouts

1. Registra motor, versión, consulta parametrizada, volumen, concurrencia y
   síntoma. Mide la línea base con datos representativos. Distingue el tiempo de
   conexión, la espera por bloqueos y el tiempo de ejecución cuando haya evidencia.
2. Usa las métricas y planes adecuados para SQL Server o PostgreSQL. Distingue
   el plan estimado de la medición con ejecución. Si una medición ejecuta la
   consulta, evalúa su coste y efectos y usa un entorno autorizado.
3. Comprueba selectividad, cardinalidades, índices, lecturas, ordenaciones,
   bloqueos y número de consultas desde la aplicación según el síntoma.
   Relaciona cada hipótesis con evidencia y prueba un cambio acotado.
4. Compara antes y después con carga, datos y parámetros equivalentes. Comprueba
   que los resultados se conservan y valora el impacto en escrituras,
   almacenamiento y otras consultas antes de proponer un cambio de esquema.
""",
)


PRODUCTION_DIAGNOSTICS = SkillDefinition(
    id="production-diagnostics",
    name="Diagnóstico de producción",
    description="Relaciona síntomas con métricas, logs y cambios y comprueba la recuperación.",
    content="""## Diagnóstico y recuperación

1. Define el síntoma, alcance, ventana temporal y comportamiento esperado.
   Anota servicios y recorridos afectados y una métrica que refleje el problema.
2. Contrasta logs, métricas, trazas y cambios recientes por hora, versión o
   identificador de correlación. Extrae solo evidencia relevante y anonimízala.
   Separa hechos, hipótesis y datos pendientes de obtener.
3. Prioriza comprobaciones que puedan descartar hipótesis con las herramientas
   y permisos disponibles. Si hace falta una intervención, describe el cambio,
   el impacto esperado y cómo revertirlo cuando corresponda.
4. Verifica la recuperación con la misma métrica y una ventana comparable.
   Comprueba el recorrido afectado y posibles efectos en dependencias. Registra
   las comprobaciones realizadas y qué señales requieren seguimiento.
""",
)

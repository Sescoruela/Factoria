# H05 · Protocolo de aceptación real

Estado: **en curso; no aceptado**. Seguimiento: [H05 #11](https://github.com/Sescoruela/Factoria/issues/11).
La preparación y las pruebas automatizadas no equivalen a una sesión autenticada.

## Preparar un laboratorio nuevo

Requisitos: checkout de Factoria, Python 3.11+, Git y el paquete instalado en el
entorno que usarás. El CLI `factoria` debe estar en PATH de la sesión externa.
El script es una herramienta de desarrollo; no forma parte del arranque de la UI.

```text
python -m venv .venv
```

Activar el entorno: `.venv\Scripts\Activate.ps1` en PowerShell o
`source .venv/bin/activate` en bash. Después, desde el checkout de Factoria:

```text
python -m pip install -e .
python tools/acceptance_lab.py preflight
python tools/acceptance_lab.py prepare ../factoria-h05-lab
```

Usa un destino que no exista y esté fuera de otro repositorio. Se crean seis repositorios
con commits locales de referencia y ramas de trabajo: fix/feature para `codex-cli`,
`opencode` y `chatgpt-checkout`. El generador no configura remotos ni inicia proveedores.
`--python-command` permite elegir el intérprete confirmado en la memoria del laboratorio.

`preflight` solo comprueba presencia en PATH. No ejecuta ayuda, versión, login ni
solicitudes a Codex/OpenCode. La presencia de un binario no demuestra autenticación.
El informe JSON empieza pendiente, sin versión/modelo ni observaciones inventados.

## Ejecutar cada caso desde una sesión nueva

1. Cierra Factoria. Inicia/autentica la herramienta por tu cuenta en la carpeta de
   prueba correspondiente. Registra versión y modelo realmente mostrados; si no se
   pueden determinar, anota desconocido y conserva la limitación.
2. Comprueba acceso al checkout, `factoria project check` y `factoria project workflows`.
   Confirma que la herramienta ve las instrucciones y recursos del proyecto.
3. Prueba primero una petición natural ambigua, sin nombrar workflow. Existen básicos
   y variantes: debe pedir aclaración antes de iniciar. Guarda el extracto observado.
4. Elige explícitamente `fix-lab` o `feature-lab`. Repite la selección mediante skill o
   comando en un laboratorio nuevo si necesitas comprobar ambos caminos sin reutilizar
   un flujo incompleto. No ejecutes dos flujos sobre el mismo proyecto.
5. Sigue `native status/next`, registra evidencias y respeta las pausas humanas. No
   utilices `factoria fix/feature` desde la sesión: iniciaría otro LLM.
6. Tras verificar y revisar, autoriza el commit local por separado. Cierra con
   `factoria native finish <id>` y comprueba historial/árbol limpio. No publiques los
   repositorios de laboratorio.

### Fix

Petición natural: «sum_even([1,2,3,4]) devuelve 4 y debería devolver 6. Corrige el fallo».
Tras la aclaración, seleccionar `fix-lab`.

Selección explícita:

- Codex: `$factoria-fix-lab Corrige sum_even conservando vacíos, negativos y cero`.
- OpenCode: `/factoria-fix-lab Corrige sum_even conservando vacíos, negativos y cero`.

La reproducción inicial falla en dos de tres pruebas. La corrección debe limitarse
al predicado de app.py y pasar las tres sin modificar las pruebas base.
Comprueba que implementation.md registra las instrucciones del agente y skill asignados.

### Feature

Petición: «Añade count_even(numbers), conservando sum_even, con el workflow feature-lab».
Alternativas: `$factoria-feature-lab` o `/factoria-feature-lab`, añadiendo esa petición.

Criterios: contar pares, incluido cero; entrada vacía devuelve 0; admitir negativos.
El agente debe mostrar el plan y detenerse. Solo después de aprobación humana puede
usar `--approve-plan`. Tras pruebas/review/documentación debe detenerse otra vez
para la aprobación final; no se concede por adelantado. El commit también se autoriza aparte.

La suite inicial de sum_even pasa, pero `python acceptance_feature.py` falla hasta
que exista la nueva función. Ambos comandos están confirmados y son obligatorios.
No cambiar tests/test_app.py ni acceptance_feature.py para forzar el aprobado.

## Casos negativos y límites

En copias nuevas, registrar:

- Ambigüedad: confirmar que pregunta qué workflow usar antes de editar/iniciar.
- Verificación fallida: dejar una implementación incorrecta; debe permanecer bloqueado
  antes de review y conservar el diagnóstico. Corregir y repetir la verificación.
- Flujo deshabilitado: bloquear su ID o tipo base, regenerar y comprobar que no arranca.
- Configuración modificada sin regenerar: debe informar de integración desactualizada.
- Feature sin aprobación posterior: no debe avanzar de approve_plan/approve_final.
- Sin checkout/shell/CLI: debe explicar el bloqueo. Con solo contexto portable,
  producir propuestas y pruebas pendientes, sin afirmar edición o ejecución reales.

La detección automática de un LLM y sus permisos externos no se demuestran solo con
el estado de Factoria. Tampoco se demuestra que hubo aprobación humana porque un
artefacto contenga un flag: se necesita el extracto de conversación correspondiente.

## Evidencia e inspección

```text
python tools/acceptance_lab.py inspect ../factoria-h05-lab/codex-cli/fix
```

La inspección lee estado, historial, referencias y marcadores. Incluso si todo lo
mecánico es correcto, devuelve `pending_human_review`, nunca aceptación automática.
No certifica identidad/modelo del proveedor, autenticación ni selección natural.
Completa acceptance-report.json con versiones/modelos observados, resultados y
referencias a extractos revisados. No adjuntes archivos de autenticación ni credenciales.

Para cerrar H05 deben estar revisados fix y feature en los tres entornos, las dos
rutas de selección, los bloqueos y el modo propuesta sin checkout. H06 depende de
ese cierre. Una prueba realizada en el agente anfitrión actual se registra como tal,
no como prueba de Codex CLI ni de OpenCode ni de arranque en una sesión nueva.

## Formatos contrastados el 05/11/2026

- [OpenAI: skills locales](https://learn.chatgpt.com/docs/build-skills): ubicación `.agents/skills`.
- [OpenCode: skills](https://opencode.ai/docs/skills/): descubrimiento compatible `.agents/skills`.
- [OpenCode: comandos](https://opencode.ai/docs/commands/): `.opencode/commands` y `$ARGUMENTS`.
- [OpenCode: agentes](https://opencode.ai/docs/agents/): `.opencode/agents` y permisos de subagentes.

La documentación confirma formatos; la aceptación depende de ejecutar las sesiones.

<!-- factoria-memory: type=active | reviewed_commit=aeb008a5b4fcfeb295c0303750f4742097a9d4fa | date=2026-10-30 | factoria=0.1.0 -->
# Verificación y pruebas

## Estado
- Framework de pruebas: `unittest` de la biblioteca estándar.
- Comando confirmado: `python -m unittest discover -s tests`.
- Los tests cubren actualmente máquina de estados, permisos, configuración, plugins y memoria de proyecto.

## Cómo comprobarlo a mano
1. Usar Python 3.11 o superior.
2. Ejecutar `python -m unittest discover -s tests` desde la raíz del repositorio.
3. Confirmar que no se añaden dependencias de runtime externas.
4. Para `memory-init`, revisar la propuesta antes de confirmar cualquier escritura.

## Limitación actual
Los tests están versionados, pero este hito todavía no añade un workflow de CI. Una ejecución no debe declararse superada sin haber lanzado el comando de pruebas en un entorno real.

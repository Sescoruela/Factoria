# Memoria de proyecto en grafo

Factoría puede indexar `AGENTS.md` y los archivos Markdown de primer nivel de
`docs/memoria/`. La base SQLite vive en `factoria/memory-graph.sqlite3` dentro
del directorio de metadatos Git del checkout. El contenido versionado sigue siendo
la fuente de referencia. Cada checkout genera su copia local.

Desde cualquier carpeta del repositorio puedes generar el índice, consultar un
tema y exportar el grafo.

```text
factoria project memory-graph build
factoria --read-only project memory-graph recall "paginación API" --limit 5
factoria --read-only project memory-graph export
factoria --read-only project memory-graph export --format mermaid
```

## Qué recoge

- Documentos y secciones con su ruta y línea de origen.
- Módulos y dependencias explícitas de las secciones **Módulos** y **Dependencias**
  de la memoria de Factoría.
- Referencias en enlaces Markdown locales y rutas entre comillas de código, si
  apuntan a archivos o carpetas del repositorio. El grafo registra la ruta.

`recall` busca términos sin distinguir mayúsculas o tildes. Devuelve fragmentos
breves, relaciones directas y nodos vecinos. `export` imprime la topología
completa. Para verla, pega la salida Mermaid en un bloque `mermaid` de tu
visor Markdown.

## Mantenerlo entre sesiones

Actualiza la memoria con el proceso habitual de Factoría y ejecuta `build`
cuando cambien sus fuentes o cambies de rama. La reconstrucción reemplaza el
índice en una transacción y elimina las entradas de documentos retirados.
Si se detecta un posible secreto en las fuentes, la generación se detiene
antes de modificar el índice.

Tras actualizar Factoría, vuelve a preparar la integración para que los
workflows de Codex y OpenCode incluyan la instrucción de consultar el grafo
cuando necesiten contexto anterior. El agente puede volver a la memoria Markdown
si el índice está pendiente de generar. Contrasta las fuentes citadas antes
de aplicar una decisión. La generación y la búsqueda usan SQLite local de
Python y relaciones explícitas. La actualización del grafo se inicia con `build`.

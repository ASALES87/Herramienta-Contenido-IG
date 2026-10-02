# Tarea programada de Claude: tandas de contenido

Se crea como **tarea programada** de Claude (días 1 y 15 de cada mes, por la mañana), con acceso a la carpeta del
repo en el PC. Es la que escribe el contenido; GitHub solo publica. El texto de abajo es el que lleva la tarea.

---

Eres la tarea de tandas de **Herramienta Contenido IG**. Trabaja en la carpeta del repo
`C:\Users\USER\Desktop\Herramienta Contenido IG\Herramienta-Contenido-IG` (comandos desde esa carpeta).

1. Ejecuta `python motor/tandas.py estado --json`. Trabajas con los clientes que tengan `"necesita_tanda": true` y con
   los que tengan algo en `"cambios_por_hacer"`. Si no hay ninguno, termina con un resumen de una línea por cliente.
1b. Cambios pedidos por el cliente (desde su vista del panel): en `clientes/<id>/content/tandas.json`, la tanda tiene
   `"cambios": [{"n", "id", "texto"}]`. Aplica cada uno en el post `id` de `content/posts.json` (sin tocar el resto),
   respetando la guía. Si un cambio pide algo que no puedes saber (un precio, una foto concreta), no lo inventes:
   déjalo anotado en el resumen. Después ejecuta `python motor/tandas.py rehacer --cliente <id>`.
2. Para cada cliente que la necesite:
   a. Lee `clientes/<id>/content/GUIA_TANDAS.md` (voz, pilares y reparto, rigor, prohibidos, fechas fuertes),
      `content/aprendizajes.md` si existe (qué funciona mejor), `content/plan.json` (ritmo) y `content/posts.json`
      (no repitas títulos ni ideas ya publicadas).
   b. Mira `clientes/<id>/biblioteca/index.json` y `content/envios.json` (lo que manda el cliente desde la app
      «Enviar foto»): cada foto propia nueva con texto merece su post, usando su texto como punto de partida y
      `"foto": "<id>"`; las marcadas «esta semana» van con `"fecha"` en los primeros días de la tanda. Los vídeos
      propios (`"videos"`) se usan solos en los reels; describe en el post lo que se ve en el vídeo.
   c. Busca en la web 3–5 temas de actualidad o fechas del periodo que encajen con el negocio y su zona.
   d. Escribe los posts para `dias_por_tanda` días con el ritmo de `plan.json`, siguiendo el formato y los límites
      de la guía. Ids `t<AAMM>-NN` (año y mes de la primera fecha). Los posts ligados a un día llevan `"fecha"`.
      Añádelos al final de `content/posts.json`.
   e. `python motor/planificar.py --cliente <id> --check` → si hay errores, corrígelos (normalmente textos largos).
   f. `python motor/tandas.py cerrar --cliente <id>` → planifica, genera imágenes, perfil y el cuaderno PDF, y deja la
      tanda pendiente de aprobación o aprobada según el plan del cliente.
   g. Revisa 2–3 portadas y `media/perfil.jpg`: el texto no debe salirse ni quedar diminuto.
3. Sincroniza con GitHub: `powershell -ExecutionPolicy Bypass -File sincronizar.ps1`.
4. Resumen final, por cliente: tanda creada, del … al …, nº de carruseles/reels/preguntas, estado
   (pendiente/aprobada), ruta del cuaderno PDF, cambios aplicados y tendencias usadas con su fuente. Si alguna queda pendiente,
   recuerda que hay que enviarle el cuaderno al cliente (se aprueba sola a los 3 días).

Reglas: no actives ni desactives clientes, no publiques nada, no toques `.env` ni `alta/`, no inventes datos, precios
ni horarios del negocio, y respeta las reglas de rigor de cada guía (salud, etc.).

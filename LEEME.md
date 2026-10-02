# Herramienta Contenido IG

Motor multi-cliente para generar y publicar contenido de Instagram de pymes. Nace del motor de Kodomo Publisher,
que sigue funcionando aparte y no se toca.

> **Estado: ensayo general.** Solo hay clientes de prueba: `demo` (Panadería La Espiga, ficticia) y `kodomo`
> (referencia para comprobar que el motor reproduce el aspecto de Kodomo; inactivo).

## Estructura
```
motor/            código común (todo lleva --cliente <id>)
  cliente.py        elige el cliente y carga su marca, rutas y credenciales
  config.py         credenciales del cliente (secretos con sufijo: IG_ACCESS_TOKEN_DEMO…)
  render.py         carruseles, historias y destacadas con la marca del cliente
  plantillas.py     5 plantillas: bloques, tipografica (color) · foto_franja, foto_completa, foto_marco (foto)
  biblioteca.py     fotos del cliente (propias o de stock Pexels/Pixabay) y a qué post va cada una
  catalogo.py       catálogo de las 5 plantillas con la marca del cliente, para que elija
  perfil.py         simula la cuadrícula del perfil para revisar el mosaico
  reels.py          reels de 30 s (vídeo de stock o propio + textos + música)
  planificar.py     coloca los posts nuevos en el calendario según plan.json
  publish.py        publica lo pendiente (solo si plan.json → "activo": true)
  media_host.py     aloja los archivos en URL pública: r2 | shopify | simulado
  comentarios.py    avisos de comentarios nuevos
  metricas.py       métricas, informe semanal y aprendizajes
  fonts/            tipografías libres por defecto (OFL)
clientes/
  _plantilla/       lo que se copia en cada alta (Fase B: alta.py)
  demo/             cliente ficticio
    marca.json      TODO lo que es de la marca
    biblioteca/     index.json + fotos (las fotos no se suben a git)
    content/        plan.json, posts.json, calendario, publicados, guía de tandas, métricas…
    media/          imágenes y vídeos generados (no se suben a git)
alta/alta.py        (Fase B) ficha del asistente → cliente montado
motor/muestras.py   muestras de presentación tras el alta
captura/            (Fase D) página «Enviar foto»
.github/workflows/  publicar.yml (todos los clientes), diario.yml (comentarios y métricas), tokens.yml, contenido.yml
motor/todos.py      lo que usan los workflows: publicar/simular todos, diario, horas de publicación → cron
tareas/tandas.md    texto de la tarea programada de Claude que escribe las tandas
sincronizar.ps1     sube a GitHub lo que escribe la tarea (como en Kodomo)
motor/tandas.py     estado de contenido de todos los clientes, cerrar y aprobar tandas
motor/tokens.py     renovación de tokens de Instagram y aviso del GH_PAT
```

## Comandos (desde la carpeta del repo)
```
python motor/planificar.py --cliente demo --dry-run   # qué se programaría
python motor/planificar.py --cliente demo             # programarlo
python motor/render.py     --cliente demo             # generar imágenes
python motor/render.py     --cliente demo --highlights
python motor/reels.py      --cliente demo r-s01-1     # montar un reel (necesita ffmpeg)
python motor/catalogo.py   --cliente demo             # catálogo de plantillas → media/catalogo.jpg
python motor/perfil.py     --cliente demo             # cuadrícula del perfil → media/perfil.jpg
python motor/revision.py   --cliente demo             # PDF numerado de la tanda para que el cliente la apruebe
python motor/biblioteca.py --cliente demo añadir foto.jpg --notas "hogaza recién hecha"
python motor/biblioteca.py --cliente demo lista
python motor/publish.py    --cliente demo upcoming 9
python motor/publish.py    --cliente demo run --dry-run
python motor/publish.py    --cliente demo next        # con media_host "simulado" no llama a Instagram
```

## Alta de un cliente (Fase B)
1. El cliente (o tú, en la llamada) rellena el asistente (`_Proyecto RRSS Pymes/asistente_alta.html`).
2. Guarda la ficha que genera (botón «Descargar ficha» o «Copiar ficha (JSON)») como `respuestas_<id>.json`.
3. `python alta/alta.py respuestas_<id>.json` → en ~1 s crea `clientes/<id>/` con:
   - `marca.json` y `content/plan.json` (colores, plantillas, nivel de fotos, ritmo, inactivo),
   - `assets/logo.png` y su versión para fondos oscuros (o claros),
   - `content/GUIA_TANDAS.md` (borrador: voz, pilares con reparto, preguntas, mitos, fechas, prohibidos, rigor por sector),
   - `CHECKLIST_<id>.md` con los pasos manuales que quedan, ya personalizados (+ diagnóstico del asistente),
   - `media/muestras/` (3 portadas, historias y mosaico del perfil) y `media/catalogo.jpg` para enseñárselo al cliente,
   - `alta/respuestas.json` con la ficha completa (datos personales: **no se sube a git**).
4. Opciones: `--id <id>` para otro identificador, `--forzar` para rehacerlo, `--sin-muestras`.

Clientes de prueba creados con `alta.py` (ficticios): `panaderia-la-espiga`, `clinica-fisio-mar` (logo, sector salud,
acceso en manos de una agencia, muchas fotos) y `taller-hermanos-ruiz` (sin Instagram, sin fotos, sin logo).

## marca.json (lo principal)
| Campo | Para qué |
|---|---|
| `colores` | `principal`, `fondo`, `acento`, `texto`. El motor calcula solo los tonos suaves y elige el color de texto legible sobre cada fondo |
| `fuentes` | archivos en `clientes/<id>/assets/fonts/` o `motor/fonts/` |
| `logo` / `logo_claro` | PNG con transparencia (el claro, para fondos oscuros). Sin logo: `logo_texto` (+ `logo_etiqueta` opcional) |
| `adorno` | `puntos`, `cubos` o `ninguno` |
| `pilares`, `pilar_pregunta` | temas; el de pregunta sale como historia |
| `destacadas`, `destacadas_sub` | a qué destacada va cada pilar y sus portadas |
| `textos` | cambia cualquier texto fijo («Desliza», «¿Sabías que…?», «Respóndenos por mensaje»…) |
| `plantillas` | una o dos de: `bloques`, `tipografica`, `foto_franja`, `foto_completa`, `foto_marco`. Una de color + una de foto = tablero foto/color. Un post puede forzar `"plantilla"` y `"foto"` |
| `media_host` | `r2` (por defecto), `shopify` o `simulado` |

## Diferencias con Kodomo Publisher
- Calendario y publicados viven en `clientes/<id>/content/`.
- `plan.json` lleva `"activo"` y la pregunta semanal se llama `pregunta` (vale también `tu_turno`).
- Los reels se programan en sus días aunque el día siguiente no haya carrusel: desarrollan el siguiente carrusel.
- Las imágenes se alojan en Cloudflare R2 (sin dependencias extra) en vez de Shopify.

## Fotos
- Propias: llegan con «Enviar foto» (Fase D) o con `biblioteca.py añadir`. Se usan antes que las de stock.
- Stock: con `PEXELS_API_KEY` o `PIXABAY_API_KEY`, el motor busca una foto por `foto_query` (o `video_query`) del post.
- Cada post guarda su foto en `content/fotos_asignadas.json`; una foto no se repite antes de 60 días.
- Sin foto disponible, el post sale con la plantilla de color.
- **Cuántas publicaciones llevan foto** depende de las fotos del cliente (`marca.json → fotos`):
  | Nivel | Feed | Dentro del carrusel |
  |---|---|---|
  | `muchas` | 3 de cada 4 con foto (las de color, en diagonal) | 2 fotos: portada + interior/cierre |
  | `mitad` | 1 de cada 2 (tablero foto / color) | la foto de portada se repite en un interior |
  | `pocas` | 1 de cada 4 (fotos en diagonal) | solo la portada; interiores de color |
  | `ninguna` | todo color (secuencia de `plan.json → mosaico`) | — |
  Con `"nivel": "auto"` el motor lo calcula con las fotos libres frente a lo que hay que publicar en 35 días,
  sin pasar de `nivel_max` (lo fija el alta según lo que dijo el cliente). Si llegan menos fotos, baja solo.
- Las casillas de color eligen su color para no coincidir con la anterior ni con la de encima.
- Lo decidido para cada publicación (plantilla, color, nivel) se guarda en `content/diseno.json` y no cambia.
- Los reels sin vídeo usan la foto del post con movimiento lento.

## Tandas
- Un post puede llevar `"fecha": "AAAA-MM-DD"` para salir ese día (fiestas, eventos); el resto se coloca alrededor.
- `revision.py` genera el cuaderno de revisión: perfil + cada publicación numerada (carrusel completo con su texto,
  guion de cada reel e historias de pregunta). El cliente responde «cambiad la 7» y listo.

## GitHub Actions (un único repo para todos los clientes)
- Secretos por cliente con sufijo: `IG_ACCESS_TOKEN_<CLIENTE>`, `IG_USER_ID_<CLIENTE>` (p. ej. `_PANADERIA_LA_ESPIGA`).
  Comunes: `IG_APP_SECRET`, `GH_PAT`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `R2_*`. Variable: `GH_PAT_CADUCA`.
  Los workflows pasan a cada cliente solo sus secretos (y los comunes), nunca los de otro.
- `publicar.yml` se lanza a las horas de los clientes (las calcula `todos.py horarios`; `alta.py` lo actualiza solo)
  y publica como mucho 1 cosa por cliente y pasada. Manual: «simular» (no publica nada, incluye clientes de ensayo)
  o «publicar_siguiente» de un cliente.
- Límites a vigilar: 100 secretos por repo (~45 clientes) y 2.000 min/mes de Actions en repos privados.

## Piloto automático (como Kodomo)
| Qué | Quién | Cuándo |
|---|---|---|
| Escribir la tanda de quien se quede sin contenido (menos de `tanda.dias_minimos_por_delante` días) | Tarea programada de Claude (`tareas/tandas.md`) + `sincronizar.ps1` | días 1 y 15 |
| Cerrar la tanda: planificar, imágenes, perfil, cuaderno PDF, registrarla | `motor/tandas.py cerrar` (lo llama la tarea) | con cada tanda |
| No publicar lo que está pendiente de aprobar | `content/tandas.json` + `publish.py` | siempre |
| Aprobar sola una tanda sin comentarios en 3 días | `contenido.yml` → `tandas.py vencidas` | cada mañana |
| Avisar si a alguien se le acaba el contenido o hay tanda pendiente | `contenido.yml` → aviso de GitHub (email) | cada mañana |
| Renovar el token de Instagram de cada cliente (≤ 20 días) | `tokens.yml` → `tokens.py renovar-todos` + `gh secret set` | lunes y jueves |
| Avisar de la caducidad del GH_PAT (no se puede renovar solo) | `tokens.yml` → `tokens.py aviso-pat` (variable `GH_PAT_CADUCA`) | 30/14/7/3/1 días antes |

Cuentan los clientes activos y los de ensayo (`plan.json → "ensayo": true`). Comandos útiles:
`python motor/tandas.py estado` · `python motor/tandas.py estado --hoy 2026-10-20` (simular fecha) ·
`python motor/tandas.py aprobar --cliente <id>` · `python motor/tokens.py estado`.

## Medidas tomadas en el ensayo
- Un reel de 30 s tarda ~1 min en montarse (sin vídeo de stock); hay que medirlo en GitHub Actions.
- Primera tanda de La Espiga (35 días: 25 carruseles, 10 reels, 5 preguntas): planificar <1 s, renderizar todo ~5 s,
  cuaderno de revisión ~4 s. Lo que lleva tiempo es escribir el contenido (lo hace la tarea de Claude).

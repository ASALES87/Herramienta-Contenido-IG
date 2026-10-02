# Guía para generar una tanda de @tallerruiz

> Borrador generado por `alta.py` a partir del cuestionario. Repásalo antes de la primera tanda.
> La lee la tarea de tandas (Claude) antes de escribir contenido.

## Marca
- **Taller Hermanos Ruiz**: Mecánica general y neumáticos en Torrent. Atiende a su barrio o ciudad.
- **Estrellas**: Revisión pre-ITV, Cambio de neumáticos, Aire acondicionado.
- **Qué le diferencia**: (preguntar).
- **Web**: no tiene.
- **Público**: Conductores de la zona.
- **Voz**: cercano. Español de España, tuteo («tú»). Frases cortas, sin tecnicismos innecesarios.
- **Objetivo**: reservas o llamadas. Llamada a la acción por defecto: «Llámanos».
- **Rigor**:
  - Nada de precios, ofertas ni horarios sin confirmarlos con el cliente.
  - No inventar datos, estudios ni normas. Si un dato no es sólido, no se usa.
  - Nada de marcas ni personas reales sin permiso.
- **Nunca**: (nada indicado).
- Emojis: pocos (nunca en las diapositivas). Hashtags: 3–5.

## Pilares (campo `pillar`)
| | Pilar | Qué es |
|---|---|---|
| P1 | Lo que hacemos | productos o servicios y cómo se hacen |
| P2 | Consejos útiles | consejos prácticos que se puedan guardar |
| P3 | Mitos y errores frecuentes | desmontar creencias frecuentes del sector |
| P4 | Equipo y día a día | quién hay detrás y cómo se trabaja |
| P5 | Clientes y opiniones | casos y momentos con clientes (con su permiso) |
| P6 | Novedades y fechas clave | novedades, temporadas y fechas fuertes |
| P7 | Tu turno | pregunta a la comunidad (va como **historia**, sin diapositivas) |

Reparto orientativo por cada 35 días (3 carruseles/semana): 3 P1 · 3 P2 · 3 P3 · 2 P4 · 2 P5 · 2 P6 · 5 P7.

## Preguntas que les hacen siempre (cada una puede ser un post)
- (sin respuesta: preguntar al cliente)

## Mitos o errores frecuentes del sector
- (sin respuesta: preguntar al cliente)

## Fechas fuertes
- (sin respuesta: preguntar al cliente)

## Cuentas que le gustan
- ninguna indicada

## Material y diseño
- Fotos propias: ninguna · fotos nuevas: no · vídeos: no · preferencia: mezcla.
- Plantillas: bloques, tipografica. Nivel de fotos previsto: todo diseño de color.
- En cada post añade `foto_query` (inglés, 3–5 palabras) por si hay que buscar una foto de stock, y `video_query` para el reel.
- Si el cliente ha enviado fotos (biblioteca/index.json), puedes asignar una con `"foto": "<id>"` cuando encaje con el tema.

## Formato de cada post (en `content/posts.json` → `posts`)
`id`, `pillar`, `title`, `slides` (2 con `h` y `body`), `fact`, `cta`, `cta_sub`, `caption`, `video_query`, `foto_query`.
Posts del pilar de pregunta (P7): solo `id`, `pillar`, `title` (la pregunta), `cta` y `caption`.
Límites: `title` 70 · `h` 60 · `body` 260 · `fact` 170 · `cta` 80 · `cta_sub` 110 · `caption` 2200.

## Pasos
1. `python motor/planificar.py --cliente taller-hermanos-ruiz --check`
2. Añade los posts al final de `clientes/taller-hermanos-ruiz/content/posts.json`.
3. `python motor/planificar.py --cliente taller-hermanos-ruiz --dry-run` y luego sin `--dry-run`.
4. `python motor/render.py --cliente taller-hermanos-ruiz` y `python motor/perfil.py --cliente taller-hermanos-ruiz`; revisa portadas y mosaico.
5. Aprobación: **solo la primera tanda la aprueba el cliente**.

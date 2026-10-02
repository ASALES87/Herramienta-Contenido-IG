# Guía para generar una tanda de @laespiga.demo

> Borrador generado por `alta.py` a partir del cuestionario. Repásalo antes de la primera tanda.
> La lee la tarea de tandas (Claude) antes de escribir contenido.

## Marca
- **Panadería La Espiga**: Pan de masa madre y bollería artesana en Ruzafa. Atiende a su barrio o ciudad.
- **Estrellas**: Hogaza de masa madre, croissant de mantequilla, coca de llanda.
- **Qué le diferencia**: Fermentación de 24 h y harina ecológica de molinos valencianos.
- **Web**: no tiene.
- **Público**: Familias del barrio de 30–45 años que buscan pan de calidad.
- **Voz**: cercano, divertido. Español de España, tuteo («tú»). Frases cortas, sin tecnicismos innecesarios.
- **Objetivo**: reservas o llamadas. Llamada a la acción por defecto: «Escríbenos por WhatsApp».
- **Rigor**:
  - Nada de precios, ofertas ni horarios sin confirmarlos con el cliente.
  - No inventar datos, estudios ni normas. Si un dato no es sólido, no se usa.
  - Nada de marcas ni personas reales sin permiso.
- **Nunca**: (nada indicado).
- Emojis: pocos (nunca en las diapositivas). Hashtags: 3–5.

## Pilares (campo `pillar`)
| | Pilar | Qué es |
|---|---|---|
| P1 | La carta y el plato estrella | lo que más piden y cómo se prepara |
| P2 | Detrás de la cocina | oficio, horarios, cómo se trabaja |
| P3 | Mitos y curiosidades | creencias frecuentes y datos curiosos del producto |
| P4 | Producto y proveedores | materias primas y de dónde vienen |
| P5 | Clientes y momentos | escenas con clientes (con su permiso) |
| P6 | Eventos y fechas | fiestas, temporadas y fechas fuertes |
| P7 | Tu turno | pregunta a la comunidad (va como **historia**, sin diapositivas) |

Reparto orientativo por cada 35 días (5 carruseles/semana): 5 P1 · 4 P2 · 4 P3 · 4 P4 · 4 P5 · 4 P6 · 5 P7.

## Preguntas que les hacen siempre (cada una puede ser un post)
- ¿Tenéis pan sin gluten? ¿Hasta qué hora hay hogaza?

## Mitos o errores frecuentes del sector
- El pan engorda
- el pan congelado pierde todo

## Fechas fuertes
- Fallas, Pascua (mona), Navidad

## Cuentas que le gustan
- ninguna indicada

## Material y diseño
- Fotos propias: algunas · fotos nuevas: cada semana · vídeos: alguno suelto · preferencia: mezcla.
- Plantillas: foto_franja, bloques. Nivel de fotos previsto: 3 de cada 4 publicaciones con foto (2 fotos por carrusel).
- En cada post añade `foto_query` (inglés, 3–5 palabras) por si hay que buscar una foto de stock, y `video_query` para el reel.
- Si el cliente ha enviado fotos (biblioteca/index.json), puedes asignar una con `"foto": "<id>"` cuando encaje con el tema.

## Formato de cada post (en `content/posts.json` → `posts`)
`id`, `pillar`, `title`, `slides` (2 con `h` y `body`), `fact`, `cta`, `cta_sub`, `caption`, `video_query`, `foto_query`.
Posts del pilar de pregunta (P7): solo `id`, `pillar`, `title` (la pregunta), `cta` y `caption`.
Límites: `title` 70 · `h` 60 · `body` 260 · `fact` 170 · `cta` 80 · `cta_sub` 110 · `caption` 2200.

## Pasos
1. `python motor/planificar.py --cliente panaderia-la-espiga --check`
2. Añade los posts al final de `clientes/panaderia-la-espiga/content/posts.json`.
3. `python motor/planificar.py --cliente panaderia-la-espiga --dry-run` y luego sin `--dry-run`.
4. `python motor/render.py --cliente panaderia-la-espiga` y `python motor/perfil.py --cliente panaderia-la-espiga`; revisa portadas y mosaico.
5. Aprobación: **solo la primera tanda la aprueba el cliente**.

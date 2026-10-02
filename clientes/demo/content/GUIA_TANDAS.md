# Guía para generar una tanda de @laespiga.demo

> Cliente FICTICIO de pruebas. La lee la tarea de tandas (Claude) antes de escribir contenido.

## Marca
- **Panadería La Espiga** (Ruzafa, Valencia): pan de masa madre y bollería artesana. Fermentación de 24 h y harina
  ecológica de molinos valencianos. Estrellas: hogaza de masa madre, croissant de mantequilla y coca de llanda.
- **Público**: familias del barrio de 30–45 años que buscan pan de calidad, sobre todo para el fin de semana.
- **Voz**: cercana y con un punto de humor. Español de España, tuteo. Frases cortas, sin tecnicismos.
- **Objetivo**: reservas y encargos por WhatsApp. Llamada a la acción por defecto: «Escríbenos por WhatsApp».
- **Rigor**: nada de afirmaciones de salud («el pan de masa madre adelgaza», «es apto para celíacos»…).
  Ningún precio u oferta sin confirmarlo con el cliente. No inventar datos ni normas.
- **Nunca**: política, comparaciones con otras panaderías.
- Emojis: pocos (1–2 en el caption, ninguno en las diapositivas). 3–5 hashtags, siempre `#LaEspigaRuzafa`.

## Pilares (campo `pillar`)
| | Pilar | Qué es |
|---|---|---|
| P1 | Nuestro pan | productos estrella y cómo se hacen |
| P2 | Detrás del obrador | horarios, oficio, el equipo |
| P3 | Mitos del pan | creencias frecuentes (engorda, congelar, integral…) |
| P4 | Consejos de casa | conservar, tostar, aprovechar el pan duro |
| P5 | Producto y proveedores | harinas, mantequilla, de dónde viene cada cosa |
| P6 | El barrio | Ruzafa, fiestas, clientes de siempre |
| P7 | Tu turno | pregunta a la comunidad (va como **historia**) |

Reparto orientativo por cada 35 días (5 carruseles/semana): 6 P1 · 4 P2 · 5 P3 · 5 P4 · 2 P5 · 3 P6 · 5 P7.

## Preguntas frecuentes de sus clientes (ideas de contenido)
- ¿Tenéis pan sin gluten? (No: se dice con claridad y sin recomendaciones de salud.)
- ¿Hasta qué hora hay hogaza?

## Mitos frecuentes
- El pan engorda. · El pan congelado pierde todo.

## Fechas fuertes
Fallas (marzo), Pascua (mona), Navidad.

## Material propio
Tiene algunas fotos y hará fotos cada semana con el enlace «Enviar foto»; puede grabar algún vídeo suelto.
Mientras no haya biblioteca, se trabaja con diseño y vídeo de stock.

## Formato de cada post
Igual que en el motor (ver `motor/LEEME.md`): `id`, `pillar`, `title`, `slides` (2 con `h` y `body`), `fact`,
`cta`, `cta_sub`, `caption`, `video_query` (inglés, escena filmable: obrador, pan, manos, horno).
Límites: `title` 70 · `h` 60 · `body` 260 · `fact` 170 · `cta` 80 · `cta_sub` 110 · `caption` 2200.

## Pasos
1. `python motor/planificar.py --cliente demo --check`
2. Añade los posts al final de `clientes/demo/content/posts.json`.
3. `python motor/planificar.py --cliente demo --dry-run` y luego sin `--dry-run`.
4. `python motor/render.py --cliente demo <ids>` y revisa 2–3 portadas.
5. Como `aprobacion` es «primera», la primera tanda se envía al cliente antes de activar.

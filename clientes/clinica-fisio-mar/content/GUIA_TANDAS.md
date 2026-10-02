# Guía para generar una tanda de @fisiomar.demo

> Borrador generado por `alta.py` a partir del cuestionario. Repásalo antes de la primera tanda.
> La lee la tarea de tandas (Claude) antes de escribir contenido.

## Marca
- **Clínica Fisio Mar**: Fisioterapia y pilates terapéutico en el Cabanyal. Atiende a su barrio o ciudad.
- **Estrellas**: Fisioterapia deportiva, Pilates terapéutico, Punción seca.
- **Qué le diferencia**: Sesiones de 50 minutos, siempre con el mismo fisio.
- **Web**: no tiene.
- **Público**: Adultos activos de 30–60 años con dolor de espalda o lesiones deportivas.
- **Voz**: profesional, cercano. Español de España, tuteo («tú»). Frases cortas, sin tecnicismos innecesarios.
- **Objetivo**: reservas o llamadas. Llamada a la acción por defecto: «Reserva tu cita».
- **Rigor**:
  - **Sector salud**: ninguna afirmación de curación ni consejo médico personal; todo lo sanitario lo valida el cliente.
  - Nada de precios, ofertas ni horarios sin confirmarlos con el cliente.
  - No inventar datos, estudios ni normas. Si un dato no es sólido, no se usa.
  - Nada de marcas ni personas reales sin permiso.
- **Nunca**: Prometer curaciones.
- Emojis: pocos (nunca en las diapositivas). Hashtags: 3–5.

## Pilares (campo `pillar`)
| | Pilar | Qué es |
|---|---|---|
| P1 | Tratamientos y servicios | qué se hace en cada servicio y para quién es |
| P2 | Consejos de prevención | hábitos y consejos generales (sin diagnóstico) |
| P3 | Mitos y errores frecuentes | desmontar creencias frecuentes del sector |
| P4 | El equipo | quién atiende y su formación |
| P5 | Preguntas frecuentes | dudas habituales antes de pedir cita |
| P6 | Novedades del centro | horarios, servicios nuevos, fechas |
| P7 | Tu turno | pregunta a la comunidad (va como **historia**, sin diapositivas) |

Reparto orientativo por cada 35 días (5 carruseles/semana): 5 P1 · 4 P2 · 4 P3 · 4 P4 · 4 P5 · 4 P6 · 5 P7.

## Preguntas que les hacen siempre (cada una puede ser un post)
- ¿Cuántas sesiones necesito?
- ¿Necesito receta médica?

## Mitos o errores frecuentes del sector
- Si duele, no hay que moverse

## Fechas fuertes
- Vuelta al cole, enero (propósitos), verano

## Cuentas que le gustan
- ninguna indicada

## Material y diseño
- Fotos propias: muchas · fotos nuevas: cada semana · vídeos: sí · preferencia: propias.
- Plantillas: foto_completa, tipografica. Nivel de fotos previsto: 3 de cada 4 publicaciones con foto (2 fotos por carrusel).
- En cada post añade `foto_query` (inglés, 3–5 palabras) por si hay que buscar una foto de stock, y `video_query` para el reel.
- Si el cliente ha enviado fotos (biblioteca/index.json), puedes asignar una con `"foto": "<id>"` cuando encaje con el tema.

## Formato de cada post (en `content/posts.json` → `posts`)
`id`, `pillar`, `title`, `slides` (2 con `h` y `body`), `fact`, `cta`, `cta_sub`, `caption`, `video_query`, `foto_query`.
Posts del pilar de pregunta (P7): solo `id`, `pillar`, `title` (la pregunta), `cta` y `caption`.
Límites: `title` 70 · `h` 60 · `body` 260 · `fact` 170 · `cta` 80 · `cta_sub` 110 · `caption` 2200.

## Pasos
1. `python motor/planificar.py --cliente clinica-fisio-mar --check`
2. Añade los posts al final de `clientes/clinica-fisio-mar/content/posts.json`.
3. `python motor/planificar.py --cliente clinica-fisio-mar --dry-run` y luego sin `--dry-run`.
4. `python motor/render.py --cliente clinica-fisio-mar` y `python motor/perfil.py --cliente clinica-fisio-mar`; revisa portadas y mosaico.
5. Aprobación: **el cliente aprueba cada tanda**.

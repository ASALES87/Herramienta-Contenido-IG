# Checklist de alta · Panadería La Espiga (`panaderia-la-espiga`)

Generada por `alta.py` desde `ficha_espiga.json`.

- [ ] Comprobar el tipo de cuenta y pasarla a profesional
- [ ] Videollamada de 20 min: invitar la cuenta como tester de la app de Meta y que acepte la invitación
- [ ] Generar el token y guardarlo: `gh secret set IG_ACCESS_TOKEN_PANADERIA_LA_ESPIGA` y `gh secret set IG_USER_ID_PANADERIA_LA_ESPIGA`
- [ ] Recoger su carpeta de fotos y darlas de alta: `python motor/biblioteca.py --cliente panaderia-la-espiga añadir …`
- [ ] Enviarle el enlace «Enviar foto» y pedirle que lo añada a la pantalla de inicio (Fase D)
- [ ] Enseñarle las muestras (`media/muestras/`) y el catálogo de plantillas (`media/catalogo.jpg`); ajustar si pide cambios
- [ ] Firmar el contrato de servicio y el de encargado del tratamiento (RGPD)
- [ ] Repasar el borrador de `content/GUIA_TANDAS.md`
- [ ] Generar la primera tanda de 35 días y enviarla a revisión

## Publicación en producción (lecciones de Kodomo)
- [ ] Lanzador externo (cron-job.org, uno solo para todos los clientes): comprobar que se dispara a las horas de este cliente (Europe/Madrid): **08:00, 10:00, 12:00, 13:30**. Si falta alguna, añadirla al mismo lanzador desde el navegador normal (cron-job.org bloquea el navegador de Claude)
- [ ] Subir a GitHub `publicar.yml` con los horarios y secretos que ha escrito `alta.py` (el cron de GitHub queda de respaldo)
- [ ] Retraso máximo acordado: `retraso_max_horas` en `content/plan.json` (ahora 3 h). Lo que llegue más tarde no se publica fuera de hora: pasa al siguiente hueco libre y llega un aviso
- [ ] Simular: Actions → «Publicar en Instagram» → modo `simular`, cliente `panaderia-la-espiga` → en verde y sin avisos raros
- [ ] Comprobación rápida: `python motor/todos.py pendiente --cliente panaderia-la-espiga` responde «si»/«no» en segundos
- [ ] Primera publicación real SOLO con confirmación explícita: modo `publicar_siguiente`, cliente `panaderia-la-espiga`. Comprobar que sale una sola vez en Instagram y que queda en `published.json` (commit «Publicado · panaderia-la-espiga»)
- [ ] Activar: `"activo": true` en `clientes/panaderia-la-espiga/content/plan.json` y subirlo a GitHub
- [ ] Avisos: confirmar que llegan por email los issues de GitHub (repo en «Watch») y los fallos de cron-job.org
- [ ] Al día siguiente de activar: el latido del resumen diario no avisa de nada pendiente y no hay issues abiertos

## Diagnóstico del asistente
- [ACCION] Cuenta de Instagram: Tu cuenta es personal. → La pasamos a profesional en el alta. No pierdes seguidores ni publicaciones.
- [OK] Conexión: Conexión con el inicio de sesión oficial de Meta. → Se hace en 20 minutos por videollamada. Nunca guardamos tu contraseña.
- [OK] Marca: Sin logo. → Usaremos tu nombre con una tipografía cuidada y tus colores.
- [OK] Colores: Paleta propuesta según tu sector. → Principal #7A3B1F, fondo #FBF4EC, acento #D9822B.
- [OK] Fotos: Tienes algunas fotos propias. → 75% de las publicaciones con foto; el resto, diseño con tus colores. Recibirás el enlace «Enviar foto» para el móvil.
- [OK] Estilo: Plantillas: Foto con franja + Bloques de color. → 3 de cada 4 publicaciones con foto (dos fotos por carrusel). Si llegan menos fotos, se ajusta solo.
- [OK] Reels: Puedes grabar algún vídeo. → Tus vídeos se usan primero; el resto con stock y música libre.

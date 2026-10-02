# Checklist de alta · Taller Hermanos Ruiz (`taller-hermanos-ruiz`)

Generada por `alta.py` desde `ficha_taller.json`.

- [ ] Crear con el cliente la cuenta profesional @tallerruiz (comprobar que el nombre está libre)
- [ ] Videollamada de 20 min: invitar la cuenta como tester de la app de Meta y que acepte la invitación
- [ ] Generar el token y guardarlo: `gh secret set IG_ACCESS_TOKEN_TALLER_HERMANOS_RUIZ` y `gh secret set IG_USER_ID_TALLER_HERMANOS_RUIZ`
- [ ] Enseñarle las muestras (`media/muestras/`) y el catálogo de plantillas (`media/catalogo.jpg`); ajustar si pide cambios
- [ ] Firmar el contrato de servicio y el de encargado del tratamiento (RGPD)
- [ ] Repasar el borrador de `content/GUIA_TANDAS.md`
- [ ] Generar la primera tanda de 35 días y enviarla a revisión

## Publicación en producción (lecciones de Kodomo)
- [ ] Lanzador externo (cron-job.org, uno solo para todos los clientes): comprobar que se dispara a las horas de este cliente (Europe/Madrid): **08:00, 10:00, 12:00, 13:30**. Si falta alguna, añadirla al mismo lanzador desde el navegador normal (cron-job.org bloquea el navegador de Claude)
- [ ] Subir a GitHub `publicar.yml` con los horarios y secretos que ha escrito `alta.py` (el cron de GitHub queda de respaldo)
- [ ] Retraso máximo acordado: `retraso_max_horas` en `content/plan.json` (ahora 3 h). Lo que llegue más tarde no se publica fuera de hora: pasa al siguiente hueco libre y llega un aviso
- [ ] Simular: Actions → «Publicar en Instagram» → modo `simular`, cliente `taller-hermanos-ruiz` → en verde y sin avisos raros
- [ ] Comprobación rápida: `python motor/todos.py pendiente --cliente taller-hermanos-ruiz` responde «si»/«no» en segundos
- [ ] Primera publicación real SOLO con confirmación explícita: modo `publicar_siguiente`, cliente `taller-hermanos-ruiz`. Comprobar que sale una sola vez en Instagram y que queda en `published.json` (commit «Publicado · taller-hermanos-ruiz»)
- [ ] Activar: `"activo": true` en `clientes/taller-hermanos-ruiz/content/plan.json` y subirlo a GitHub
- [ ] Avisos: confirmar que llegan por email los issues de GitHub (repo en «Watch») y los fallos de cron-job.org
- [ ] Al día siguiente de activar: el latido del resumen diario no avisa de nada pendiente y no hay issues abiertos

## Diagnóstico del asistente
- [ACCION] Cuenta de Instagram: No tienes cuenta todavía. → La creamos como cuenta profesional con el nombre @tallerruiz en la videollamada de alta.
- [OK] Conexión: Conexión con el inicio de sesión oficial de Meta. → Se hace en 20 minutos por videollamada. Nunca guardamos tu contraseña.
- [OK] Marca: Sin logo. → Usaremos tu nombre con una tipografía cuidada y tus colores.
- [OK] Colores: Paleta propuesta según tu sector. → Principal #263238, fondo #F2F3F4, acento #E85D04.
- [OK] Fotos: No tienes fotos propias. → Diseño con tus colores; si algún día nos mandas fotos, las incorporamos.
- [OK] Estilo: Plantillas: Bloques de color + Tipográfica. → Todo diseño con tus colores, sin depender de fotos.
- [OK] Reels: No vas a grabar vídeos. → Reels de 30 s con vídeo de stock, tus textos y música libre. No sales en cámara.

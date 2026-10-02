# Checklist de alta · Clínica Fisio Mar (`clinica-fisio-mar`)

Generada por `alta.py` desde `ficha_fisio.json`.

- [ ] Enviar al cliente el mensaje para pedir el acceso a su agencia o a quien lleve la cuenta
- [ ] Videollamada de 20 min: invitar la cuenta como tester de la app de Meta y que acepte la invitación
- [ ] Generar el token y guardarlo: `gh secret set IG_ACCESS_TOKEN_CLINICA_FISIO_MAR` y `gh secret set IG_USER_ID_CLINICA_FISIO_MAR`
- [ ] Recoger su carpeta de fotos y darlas de alta: `python motor/biblioteca.py --cliente clinica-fisio-mar añadir …`
- [ ] Enviarle el enlace «Enviar foto» y pedirle que lo añada a la pantalla de inicio (Fase D)
- [ ] Revisar en GUIA_TANDAS.md la regla de afirmaciones sanitarias
- [ ] Enseñarle las muestras (`media/muestras/`) y el catálogo de plantillas (`media/catalogo.jpg`); ajustar si pide cambios
- [ ] Firmar el contrato de servicio y el de encargado del tratamiento (RGPD)
- [ ] Repasar el borrador de `content/GUIA_TANDAS.md`
- [ ] Generar la primera tanda de 35 días y enviarla a revisión
- [ ] Activar: `"activo": true` en `clientes/clinica-fisio-mar/content/plan.json`

## Diagnóstico del asistente
- [OK] Cuenta de Instagram: Cuenta profesional activa. → Lista para conectar.
- [ACCION] Conexión: La cuenta la lleva otra persona o una agencia. → Te damos el mensaje para pedirle el acceso. Sin eso no podemos conectar.
- [OK] Marca: Logo recibido. → Lo usamos en portadas, historias y destacadas.
- [OK] Colores: Colores sacados de tu logo. → Principal #304848, fondo #F4F8F8, acento #F0A848.
- [OK] Fotos: Tienes muchas fotos propias. → 75% de las publicaciones con foto; el resto, diseño con tus colores. Recibirás el enlace «Enviar foto» para el móvil.
- [OK] Estilo: Plantillas: Foto completa + Tipográfica. → 3 de cada 4 publicaciones con foto (dos fotos por carrusel). Si llegan menos fotos, se ajusta solo.
- [OK] Reels: Puedes grabar vídeos. → Tus vídeos se usan primero; el resto con stock y música libre.
- [ACCION] Contenido sensible: Sector salud. → Las afirmaciones sanitarias se publican solo con tu validación.

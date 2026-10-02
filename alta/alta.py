"""Alta de un cliente nuevo a partir de la ficha del asistente (respuestas_<id>.json).

Uso (desde la carpeta del repo):
  python alta/alta.py respuestas_panaderia-la-espiga.json            → clientes/<id>/ listo
  python alta/alta.py ficha.json --id espiga --forzar                 → otro id / rehacer un alta
  python alta/alta.py ficha.json --sin-muestras                       → sin generar imágenes

Qué hace (en un solo comando):
  1. Crea clientes/<id>/ desde clientes/_plantilla/.
  2. marca.json y plan.json con lo que calculó el asistente (colores, plantillas, nivel de fotos, ritmo…).
  3. Logo: lo guarda en assets/logo.png y prepara la versión para fondos oscuros (o claros).
  4. Borrador de content/GUIA_TANDAS.md con la voz, pilares, preguntas, mitos, fechas y prohibidos.
  5. CHECKLIST_<id>.md con los pasos manuales que quedan, ya personalizados.
  6. Muestras (3 portadas, historias, mosaico) y catálogo de plantillas para enseñárselo al cliente.
Las respuestas completas (con datos de contacto) se guardan en clientes/<id>/alta/, que NO se sube a git.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTES = ROOT / "clientes"
PLANTILLA = CLIENTES / "_plantilla"

ZONA = {"local": "su barrio o ciudad", "provincia": "su provincia", "espana": "toda España", "online": "solo online"}
OBJETIVO = {"reservas": "reservas o llamadas", "web": "visitas a la web", "ventas": "ventas online", "notoriedad": "que les conozcan"}
TIEMPO = {"nada": "casi nada (que funcione solo)", "15": "unos 15 minutos a la semana", "60": "1 hora o más a la semana"}
FOTOS = {"muchas": "muchas", "algunas": "algunas", "no": "ninguna"}
NUEVAS = {"semana": "cada semana", "mes": "cada mes", "no": "no"}
VIDEOS = {"si": "sí", "alguno": "alguno suelto", "no": "no"}
NIVEL_TXT = {"muchas": "3 de cada 4 publicaciones con foto (2 fotos por carrusel)", "mitad": "1 de cada 2 con foto (tablero)",
             "pocas": "1 de cada 4 con foto, solo en portada", "ninguna": "todo diseño de color"}
DESC_PILAR = {
    "Tu turno": "pregunta a la comunidad (va como **historia**, sin diapositivas)",
    "Lo que hacemos": "productos o servicios y cómo se hacen", "Qué hacemos": "productos o servicios y cómo se hacen",
    "Consejos útiles": "consejos prácticos que se puedan guardar", "Mitos y errores frecuentes": "desmontar creencias frecuentes del sector",
    "Equipo y día a día": "quién hay detrás y cómo se trabaja", "Clientes y opiniones": "casos y momentos con clientes (con su permiso)",
    "Novedades y fechas clave": "novedades, temporadas y fechas fuertes",
    "La carta y el plato estrella": "lo que más piden y cómo se prepara", "Detrás de la cocina": "oficio, horarios, cómo se trabaja",
    "Mitos y curiosidades": "creencias frecuentes y datos curiosos del producto", "Producto y proveedores": "materias primas y de dónde vienen",
    "Clientes y momentos": "escenas con clientes (con su permiso)", "Eventos y fechas": "fiestas, temporadas y fechas fuertes",
    "Tratamientos y servicios": "qué se hace en cada servicio y para quién es", "Consejos de prevención": "hábitos y consejos generales (sin diagnóstico)",
    "El equipo": "quién atiende y su formación", "Preguntas frecuentes": "dudas habituales antes de pedir cita",
    "Novedades del centro": "horarios, servicios nuevos, fechas",
    "Antes y después": "resultados reales (con permiso del cliente)", "Tendencias": "lo que se lleva esta temporada",
    "Consejos de cuidado": "cómo mantener el resultado en casa", "Clientas y clientes": "experiencias (con su permiso)",
    "Ofertas y fechas": "campañas y fechas (precios siempre validados)",
    "Cursos y grupos": "qué se enseña y a quién va dirigido", "Consejos de estudio": "técnicas y hábitos de estudio",
    "Errores frecuentes": "errores habituales y cómo evitarlos", "Profesores y día a día": "quién enseña y cómo son las clases",
    "Logros del alumnado": "resultados (con permiso)", "Plazos y matrículas": "fechas de inscripción y novedades",
    "Producto estrella": "el producto que más se vende y por qué", "Cómo se usa": "tutoriales y usos",
    "Consejos y mitos": "consejos y creencias frecuentes", "Detrás de la marca": "historia, valores y cómo se trabaja",
    "Opiniones": "opiniones reales de clientes (con permiso)", "Lanzamientos y ofertas": "novedades y campañas",
}


def slug(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "cliente").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:30] or "cliente"


def lineas(txt, comas: bool = False) -> list[str]:
    """Separa una respuesta en elementos: por líneas o «;» (y por comas si comas=True y es una sola línea)."""
    trozos = [x.strip(" -•\t") for x in re.split(r"[\n;]+", txt or "") if x.strip(" -•\t")]
    if comas and len(trozos) == 1 and "," in trozos[0]:
        trozos = [x.strip() for x in re.split(r",| y ", trozos[0]) if x.strip()]
    return trozos


# ---------- logo ----------

def guardar_logo(data_url: str, dest: Path, colores: dict) -> dict:
    """Guarda el logo y crea la versión para el fondo contrario (blanca si el logo es oscuro, y viceversa)."""
    from PIL import Image
    raw = base64.b64decode(data_url.split(",", 1)[1])
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    dest.mkdir(parents=True, exist_ok=True)
    im.save(dest / "logo.png")
    from PIL import ImageStat
    alfa = im.getchannel("A")
    visible = alfa.point(lambda v: 255 if v > 128 else 0)
    if not visible.getbbox():
        return {"logo": "assets/logo.png"}
    r_, g_, b_ = ImageStat.Stat(im.convert("RGB"), visible).mean
    lum = (0.2126 * r_ + 0.7152 * g_ + 0.0722 * b_) / 255
    # ¿tiene fondo opaco (sin transparencia)? entonces no se puede recolorear: se usa tal cual
    transparente = sum(alfa.histogram()[:20]) > 0.05 * im.width * im.height
    if not transparente:
        return {"logo": "assets/logo.png", "logo_claro": "assets/logo.png"}
    color = (255, 255, 255) if lum < 0.5 else tuple(int(colores.get("texto", "#222222")[i:i + 2], 16) for i in (1, 3, 5))
    otro = Image.new("RGBA", im.size, color + (0,))
    otro.putalpha(im.getchannel("A"))
    nombre = "logo_claro.png" if lum < 0.5 else "logo_oscuro.png"
    otro.save(dest / nombre)
    if lum < 0.5:
        return {"logo": "assets/logo.png", "logo_claro": "assets/logo_claro.png"}
    return {"logo": "assets/logo_oscuro.png", "logo_claro": "assets/logo.png"}


# ---------- guía de tandas ----------

def guia(r: dict, marca: dict, plan: dict) -> str:
    nombre, user = marca["nombre"], marca.get("instagram") or "(cuenta por crear)"
    trato = "tuteo («tú»)" if r.get("trato") != "usted" else "trato de usted"
    tono = ", ".join(r.get("tono") or ["cercano"])
    pil = marca["pilares"]
    preg = marca.get("pilar_pregunta")
    normales = [k for k in pil if k != preg]
    car = len(plan["carrusel"]["dias"]) * 5
    base, resto = divmod(car, max(1, len(normales)))
    reparto = " · ".join(f"{base + (1 if i < resto else 0)} {k}" for i, k in enumerate(normales)) + (f" · 5 {preg}" if preg else "")
    filas = "\n".join(f"| {k} | {v} | {DESC_PILAR.get(v, '')} |" for k, v in pil.items())
    lista = lambda t, vacio="(sin respuesta: preguntar al cliente)": "\n".join(f"- {x}" for x in lineas(t)) or f"- {vacio}"
    rigor = ["Nada de precios, ofertas ni horarios sin confirmarlos con el cliente.",
             "No inventar datos, estudios ni normas. Si un dato no es sólido, no se usa.",
             "Nada de marcas ni personas reales sin permiso."]
    if r.get("sector") == "salud":
        rigor.insert(0, "**Sector salud**: ninguna afirmación de curación ni consejo médico personal; todo lo sanitario lo valida el cliente.")
    fotos_txt = (f"Fotos propias: {FOTOS.get(r.get('fotos'), '?')} · fotos nuevas: {NUEVAS.get(r.get('fotosNuevas'), '?')} · "
                 f"vídeos: {VIDEOS.get(r.get('videos'), '?')} · preferencia: {r.get('preferencia', 'mezcla')}.")
    nivel = (marca.get("fotos") or {}).get("nivel_max", "ninguna")
    return f"""# Guía para generar una tanda de @{user}

> Borrador generado por `alta.py` a partir del cuestionario. Repásalo antes de la primera tanda.
> La lee la tarea de tandas (Claude) antes de escribir contenido.

## Marca
- **{nombre}**: {r.get('actividad', '')}. Atiende a {ZONA.get(r.get('zona'), 'su zona')}.
- **Estrellas**: {', '.join(lineas(r.get('estrella'), comas=True)) or '(preguntar)'}.
- **Qué le diferencia**: {r.get('diferencia') or '(preguntar)'}.
- **Web**: {r.get('web') or 'no tiene'}.
- **Público**: {r.get('clienteIdeal') or '(preguntar)'}.
- **Voz**: {tono}. Español de España, {trato}. Frases cortas, sin tecnicismos innecesarios.
- **Objetivo**: {OBJETIVO.get(r.get('objetivo'), '')}. Llamada a la acción por defecto: «{marca.get('cta_por_defecto', '')}».
- **Rigor**:
{chr(10).join('  - ' + x for x in rigor)}
- **Nunca**: {r.get('prohibidos') or '(nada indicado)'}.
- Emojis: {r.get('emojis', 'pocos')} (nunca en las diapositivas). Hashtags: 3–5{', siempre ' + r['hashtags'] if r.get('hashtags') else ''}.

## Pilares (campo `pillar`)
| | Pilar | Qué es |
|---|---|---|
{filas}

Reparto orientativo por cada 35 días ({len(plan['carrusel']['dias'])} carruseles/semana): {reparto}.

## Preguntas que les hacen siempre (cada una puede ser un post)
{lista(r.get('preguntas'))}

## Mitos o errores frecuentes del sector
{lista(r.get('mitos'))}

## Fechas fuertes
{lista(r.get('fechas'))}

## Cuentas que le gustan
{lista(r.get('referencias'), 'ninguna indicada')}

## Material y diseño
- {fotos_txt}
- Plantillas: {', '.join(marca.get('plantillas', []))}. Nivel de fotos previsto: {NIVEL_TXT.get(nivel, nivel)}.
- En cada post añade `foto_query` (inglés, 3–5 palabras) por si hay que buscar una foto de stock, y `video_query` para el reel.
- Si el cliente ha enviado fotos (biblioteca/index.json), puedes asignar una con `"foto": "<id>"` cuando encaje con el tema.

## Formato de cada post (en `content/posts.json` → `posts`)
`id`, `pillar`, `title`, `slides` (2 con `h` y `body`), `fact`, `cta`, `cta_sub`, `caption`, `video_query`, `foto_query`
y, si el post va ligado a un día (una fiesta, un evento), `fecha` (AAAA-MM-DD; debe ser día de carrusel).
Posts del pilar de pregunta ({preg}): solo `id`, `pillar`, `title` (la pregunta), `cta` y `caption`.
Límites: `title` 70 · `h` 60 · `body` 260 · `fact` 170 · `cta` 80 · `cta_sub` 110 · `caption` 2200.

## Pasos
1. `python motor/planificar.py --cliente {marca['id']} --check`
2. Añade los posts al final de `clientes/{marca['id']}/content/posts.json`.
3. `python motor/planificar.py --cliente {marca['id']} --dry-run` y luego sin `--dry-run`.
4. `python motor/render.py --cliente {marca['id']}` y `python motor/perfil.py --cliente {marca['id']}`; revisa portadas y mosaico.
5. `python motor/revision.py --cliente {marca['id']}` → PDF numerado para que el cliente lo revise.
6. Aprobación: **{ {'cada': 'el cliente aprueba cada tanda', 'primera': 'solo la primera tanda la aprueba el cliente', 'no': 'sin aprobación (temas sensibles se consultan igual)'}.get(r.get('aprobacion'), 'primera') }**.
"""


# ---------- checklist ----------

def produccion(cid: str, plan: dict) -> list[str]:
    """Pasos de puesta en producción (lecciones de Kodomo, oct-2026). Ver LEEME → «Publicación en producción»."""
    horas = sorted({(plan.get(k) or {}).get("hora") for k in ("carrusel", "dato", "pregunta", "tu_turno", "reels")} - {None})
    return [
        f"Lanzador externo (cron-job.org, uno solo para todos los clientes): comprobar que se dispara a las horas de este "
        f"cliente (Europe/Madrid): **{', '.join(horas) or '—'}**. Si falta alguna, añadirla al mismo lanzador desde el "
        f"navegador normal (cron-job.org bloquea el navegador de Claude)",
        "Subir a GitHub `publicar.yml` con los horarios y secretos que ha escrito `alta.py` (el cron de GitHub queda de respaldo)",
        f"Retraso máximo acordado: `retraso_max_horas` en `content/plan.json` (ahora {plan.get('retraso_max_horas', 3)} h). "
        f"Lo que llegue más tarde no se publica fuera de hora: pasa al siguiente hueco libre y llega un aviso",
        f"Simular: Actions → «Publicar en Instagram» → modo `simular`, cliente `{cid}` → en verde y sin avisos raros",
        f"Comprobación rápida: `python motor/todos.py pendiente --cliente {cid}` responde «si»/«no» en segundos",
        f"Primera publicación real SOLO con confirmación explícita: modo `publicar_siguiente`, cliente `{cid}`. "
        f"Comprobar que sale una sola vez en Instagram y que queda en `published.json` (commit «Publicado · {cid}»)",
        f"Activar: `\"activo\": true` en `clientes/{cid}/content/plan.json` y subirlo a GitHub",
        "Avisos: confirmar que llegan por email los issues de GitHub (repo en «Watch») y los fallos de cron-job.org",
        "Al día siguiente de activar: el latido del resumen diario no avisa de nada pendiente y no hay issues abiertos",
    ]


def checklist(r: dict, marca: dict, ficha: Path, plan: dict | None = None) -> str:
    cid, ID = marca["id"], marca["id"].upper().replace("-", "_")
    L = []
    if r.get("tieneIG") == "no":
        L.append(f"Crear con el cliente la cuenta profesional {r.get('usuarioDeseado', '')} (comprobar que el nombre está libre)")
    if r.get("tipoCuenta") in ("personal", "nose"):
        L.append("Comprobar el tipo de cuenta y pasarla a profesional")
    if r.get("quienAcceso") == "otra":
        L.append("Enviar al cliente el mensaje para pedir el acceso a su agencia o a quien lleve la cuenta")
    if r.get("quienAcceso") == "perdido":
        L.append("Confirmar que ha recuperado la contraseña antes de la videollamada")
    if r.get("paginaFB") == "suelta":
        L.append("Vincular su página de Facebook con Instagram")
    L.append("Videollamada de 20 min: invitar la cuenta como tester de la app de Meta y que acepte la invitación")
    L.append(f"Generar el token y guardarlo: `gh secret set IG_ACCESS_TOKEN_{ID}` y `gh secret set IG_USER_ID_{ID}`")
    if r.get("tieneLogo") == "si" and not r.get("logo"):
        L.append("Pedir el logo en PNG con fondo transparente y guardarlo en `assets/logo.png`")
    if r.get("tipografia") == "propia":
        L.append("Pedir los archivos de su tipografía, comprobar la licencia y ponerlos en `assets/fonts/`")
    if r.get("fotos") in ("muchas", "algunas"):
        L.append(f"Recoger su carpeta de fotos y darlas de alta: `python motor/biblioteca.py --cliente {cid} añadir …`")
    if r.get("fotosNuevas") in ("semana", "mes"):
        L.append("Enviarle el enlace «Enviar foto» y pedirle que lo añada a la pantalla de inicio (Fase D)")
    if r.get("sector") == "salud":
        L.append("Revisar en GUIA_TANDAS.md la regla de afirmaciones sanitarias")
    L += ["Enseñarle las muestras (`media/muestras/`) y el catálogo de plantillas (`media/catalogo.jpg`); ajustar si pide cambios",
          "Firmar el contrato de servicio y el de encargado del tratamiento (RGPD)",
          "Repasar el borrador de `content/GUIA_TANDAS.md`",
          "Generar la primera tanda de 35 días y enviarla a revisión"]
    diag = "\n".join(f"- [{x['estado'].upper()}] {x['area']}: {x['situacion']} → {x['solucion']}" for x in r.get("_diagnostico", []))
    return (f"# Checklist de alta · {marca['nombre']} (`{cid}`)\n\nGenerada por `alta.py` desde `{ficha.name}`.\n\n"
            + "\n".join(f"- [ ] {x}" for x in L)
            + "\n\n## Publicación en producción (lecciones de Kodomo)\n"
            + "\n".join(f"- [ ] {x}" for x in produccion(cid, plan or {}))
            + (f"\n\n## Diagnóstico del asistente\n{diag}\n" if diag else "\n"))


# ---------- textos de muestra ----------

def muestras(r: dict, marca: dict) -> dict:
    """Tres posts de muestra (solo para las imágenes de presentación, no se publican)."""
    est = lineas(r.get("estrella"), comas=True) or [marca["nombre"]]
    mitos = lineas(r.get("mitos"))
    preguntas = lineas(r.get("preguntas"))
    pil = [k for k in marca["pilares"] if k != marca.get("pilar_pregunta")] or list(marca["pilares"])
    buscar = lambda *ws: next((k for k in pil if any(w in marca["pilares"][k].lower() for w in ws)), None)
    corto = lambda s, n: s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"
    may = lambda s: s[:1].upper() + s[1:]
    base = {"slides": [{"h": "Así lo hacemos", "body": r.get("diferencia") or r.get("actividad") or ""},
                       {"h": "Por qué te importa", "body": r.get("clienteIdeal") or ""}],
            "fact": corto(r.get("diferencia") or r.get("actividad") or marca["nombre"], 160),
            "cta": "¿Lo sabías?", "caption": ""}
    posts = [
        {**base, "id": "m1", "pillar": pil[0], "title": corto(may(est[0]), 70)},
        {**base, "id": "m2", "pillar": buscar("mito", "error", "curios") or pil[min(2, len(pil) - 1)],
         "title": corto("Mito: " + mitos[0][:1].lower() + mitos[0][1:], 70) if mitos else corto(f"Lo que nadie te cuenta: {est[0]}", 70)},
        {**base, "id": "m3", "pillar": buscar("consejo", "pregunta", "duda") or pil[min(1, len(pil) - 1)],
         "title": corto(preguntas[0], 70) if preguntas else corto(may(est[1] if len(est) > 1 else est[0]), 70)},
    ]
    if marca.get("pilar_pregunta"):
        posts.append({"id": "m4", "pillar": marca["pilar_pregunta"], "title": "¿Qué te gustaría que te contáramos por aquí?",
                      "cta": "Cuéntanoslo por mensaje", "caption": ""})
    return {"_nota": "Textos de muestra para las imágenes de presentación. No se publican.", "posts": posts}


# ---------- alta ----------

def main():
    ap = argparse.ArgumentParser(description="Alta de cliente desde la ficha del asistente")
    ap.add_argument("ficha")
    ap.add_argument("--id")
    ap.add_argument("--forzar", action="store_true", help="rehacer el alta si el cliente ya existe")
    ap.add_argument("--sin-muestras", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    ficha = Path(a.ficha)
    r = json.loads(ficha.read_text(encoding="utf-8"))
    if "_marca" not in r or "_plan" not in r:
        sys.exit("La ficha no trae _marca/_plan: expórtala con la versión actual del asistente.")
    marca, plan = r["_marca"], r["_plan"]
    cid = slug(a.id or marca.get("id") or r.get("nombre"))
    marca["id"] = cid
    dest = CLIENTES / cid
    if dest.exists():
        if not a.forzar:
            sys.exit(f"Ya existe clientes/{cid}. Usa --forzar para rehacerlo (se borra lo que haya).")
        shutil.rmtree(dest)
    shutil.copytree(PLANTILLA, dest)

    faltan = [k for k, n in (("nombre", "nombre"), ("actividad", "actividad"), ("email", "email"), ("okDatos", "conformidad de datos"),
                             ("okConexion", "conformidad de conexión")) if not r.get(k)]

    base = json.loads((dest / "marca.json").read_text(encoding="utf-8"))
    base.update({k: v for k, v in marca.items() if v is not None or k in ("logo", "logo_claro")})
    base["_nota"] = f"Generado por alta.py el {time.strftime('%d/%m/%Y')} desde {ficha.name}."
    if r.get("logo"):
        base.update(guardar_logo(r["logo"], dest / "assets", base["colores"]))
    (dest / "marca.json").write_text(json.dumps(base, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    p0 = json.loads((dest / "content" / "plan.json").read_text(encoding="utf-8"))
    p0.update(plan)
    p0["activo"] = False
    (dest / "content" / "plan.json").write_text(json.dumps(p0, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for nombre, vacio in (("posts.json", {"posts": []}), ("reels.json", {"reels": []})):
        (dest / "content" / nombre).write_text(json.dumps(vacio, indent=1) + "\n", encoding="utf-8")
    (dest / "biblioteca").mkdir(exist_ok=True)
    (dest / "biblioteca" / "index.json").write_text('{"fotos": []}\n', encoding="utf-8")
    (dest / "content" / "GUIA_TANDAS.md").write_text(guia(r, base, p0), encoding="utf-8")
    (dest / "content" / "muestras.json").write_text(json.dumps(muestras(r, base), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (dest / f"CHECKLIST_{cid}.md").write_text(checklist(r, base, ficha, p0), encoding="utf-8")
    priv = dest / "alta"
    priv.mkdir(exist_ok=True)
    shutil.copy(ficha, priv / "respuestas.json")   # datos personales: carpeta excluida de git

    print(f"✓ Cliente creado: clientes/{cid}  ({base['nombre']}, @{base.get('instagram') or 'sin cuenta'})")
    print(f"  plantillas {', '.join(base.get('plantillas', []))} · fotos hasta «{(base.get('fotos') or {}).get('nivel_max')}» · ritmo {p0.get('ritmo')}")
    if faltan:
        print(f"  ⚠ Faltan en la ficha: {', '.join(faltan)}")
    if not a.sin_muestras:
        for script in ("muestras.py", "catalogo.py"):
            res = subprocess.run([sys.executable, str(ROOT / "motor" / script), "--cliente", cid], capture_output=True, text=True)
            print("  " + (res.stdout.strip().splitlines() or [""])[-1] if res.returncode == 0 else f"  ✗ {script}: {res.stderr.strip()[-300:]}")
    if (ROOT / ".github" / "workflows" / "publicar.yml").exists():
        for orden in ("horarios", "secretos"):   # horas de publicación y secretos del cliente nuevo en los workflows
            res = subprocess.run([sys.executable, str(ROOT / "motor" / "todos.py"), orden, "--escribir"], capture_output=True, text=True)
            print("  " + (res.stdout.strip().splitlines() or [""])[-1])
    print(f"  Siguiente: abre clientes/{cid}/CHECKLIST_{cid}.md")
    print(f"  Tiempo: {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()

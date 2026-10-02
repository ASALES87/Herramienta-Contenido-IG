"""Cuaderno de revisión de una tanda, para que el cliente la apruebe (PDF).

Uso:  python revision.py --cliente <id> [--desde AAAA-MM-DD] [--hasta AAAA-MM-DD]
      → clientes/<id>/media/revision_<desde>_<hasta>.pdf

Página 1: cómo quedará el perfil (mosaico) y resumen de la tanda.
Después, por orden de publicación: cada carrusel (5 diapositivas + texto de la publicación),
cada reel (portada + guion) y las historias de pregunta. Cada publicación lleva su número para
que el cliente pueda decir «cambiad la 7» sin más.
"""
import argparse
import json
import re
from datetime import date, datetime

from PIL import Image, ImageDraw, ImageOps

import cliente as C
import render as R

PW, PH, MG = 1240, 1754, 70   # A4 a 150 ppp
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
TIPO = {"carousel": "Carrusel", "reel": "Reel", "story": "Historia"}


def fecha_txt(dt):
    return f"{DIAS[dt.weekday()]} {dt.day} de {MESES[dt.month]} · {dt.strftime('%H:%M')}"


EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")


def texto(d, xy, t, size, color="#222222", bold=False, ancho=PW - 2 * MG, lh=1.35):
    """Texto con salto de línea. Quita los emojis: la tipografía del PDF no los tiene."""
    t = re.sub(r" +", " ", EMOJI.sub("", t or ""))
    f = R.semi_font(size) if bold else R.body_font(size)
    x, y = xy
    for ln in R.wrap(d, t, f, ancho):
        d.text((x, y), ln, font=f, fill=color)
        y += int(size * lh)
    return y


class Cuaderno:
    def __init__(self):
        self.paginas = []
        self.nueva()

    def nueva(self):
        self.pag = Image.new("RGB", (PW, PH), "#FFFFFF")
        self.d = ImageDraw.Draw(self.pag)
        self.y = MG
        self.paginas.append(self.pag)
        pie = f"{C.MARCA.get('nombre', '')} · revisión de contenido · página {len(self.paginas)}"
        self.d.text((MG, PH - 50), pie, font=R.body_font(18), fill="#999999")

    def sitio(self, alto):
        if self.y + alto > PH - 80:
            self.nueva()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde")
    ap.add_argument("--hasta")
    a = ap.parse_args()
    R.ensure_fonts()
    cal = json.loads(C.CAL.read_text(encoding="utf-8"))["posts"]
    posts = {p["id"]: p for p in json.loads(C.POSTS.read_text(encoding="utf-8"))["posts"]}
    reels = {r["id"]: r for r in json.loads(C.REELS.read_text(encoding="utf-8"))["reels"]}
    desde = date.fromisoformat(a.desde) if a.desde else min(datetime.fromisoformat(e["publish_at"]).date() for e in cal)
    hasta = date.fromisoformat(a.hasta) if a.hasta else max(datetime.fromisoformat(e["publish_at"]).date() for e in cal)
    items = sorted((e for e in cal if desde <= datetime.fromisoformat(e["publish_at"]).date() <= hasta
                    and not e.get("skip") and not e["id"].startswith("f-")), key=lambda e: e["publish_at"])

    cu = Cuaderno()
    d = cu.d
    d.text((MG, cu.y), f"Contenido para revisar · {C.MARCA.get('nombre', '')}", font=R.title_font(46), fill=R.TITULO_FONDO)
    cu.y += 70
    n = {k: sum(1 for e in items if e["type"] == k) for k in ("carousel", "reel", "story")}
    cu.y = texto(d, (MG, cu.y), f"Del {desde.day} de {MESES[desde.month]} al {hasta.day} de {MESES[hasta.month]} de {hasta.year}: "
                 f"{n['carousel']} carruseles, {n['reel']} reels y {n['story']} historias de pregunta. Además, cada carrusel "
                 f"lleva su historia «{C.texto('dato')}» por la mañana.", 24, "#444444")
    cu.y = texto(d, (MG, cu.y + 10), "Cómo revisarlo: si algo no te convence, dinos el número de la publicación y qué cambiarías. "
                 "Lo que no nos comentes en 3 días se publica tal cual.", 24, "#444444")
    perfil = C.MEDIA / "perfil.jpg"
    if perfil.exists():
        im = Image.open(perfil)
        w = PW - 2 * MG - 200
        im = im.resize((w, int(im.height * w / im.width)))
        if cu.y + 60 + im.height > PH - 100:
            im = im.resize((int(im.width * (PH - 160 - cu.y - 60) / im.height), PH - 160 - cu.y - 60))
        d.text((MG, cu.y + 20), "Así quedará tu perfil", font=R.semi_font(26), fill="#222222")
        cu.pag.paste(im, ((PW - im.width) // 2, cu.y + 60))

    cu.nueva()   # las publicaciones empiezan en la página 2
    for num, e in enumerate(items, 1):
        dt = datetime.fromisoformat(e["publish_at"])
        if e["type"] == "carousel":
            p = posts.get(e["id"], {})
            cu.sitio(820)
            d = cu.d
            d.text((MG, cu.y), f"{num}. {TIPO[e['type']]} · {fecha_txt(dt)}", font=R.semi_font(24), fill=R.ACENTO)
            cu.y += 44
            tw = (PW - 2 * MG - 4 * 12) // 5
            for i in range(1, 6):
                f = C.MEDIA / "carousels" / e["id"] / f"{i:02d}.jpg"
                if f.exists():
                    cu.pag.paste(ImageOps.fit(Image.open(f), (tw, int(tw * 1.25))), (MG + (i - 1) * (tw + 12), cu.y))
            cu.y += int(tw * 1.25) + 20
            cu.y = texto(d, (MG, cu.y), p.get("caption", ""), 21, "#333333", lh=1.3) + 40
            d.line((MG, cu.y - 20, PW - MG, cu.y - 20), fill="#E5E5E5", width=2)
        elif e["type"] == "reel":
            r = reels.get(e["id"], {})
            p = posts.get(r.get("twin"), {})
            cu.sitio(560)
            d = cu.d
            d.text((MG, cu.y), f"{num}. Reel de 30 s · {fecha_txt(dt)}", font=R.semi_font(24), fill=R.ACENTO)
            cu.y += 44
            cov = C.MEDIA / "reels" / f"{e['id']}_cover.jpg"
            if not cov.exists():
                import reels as RL
                cov = RL.cover(e["id"])
            im = ImageOps.fit(Image.open(cov), (270, 480))
            cu.pag.paste(im, (MG, cu.y))
            x = MG + 300
            guion = [("0–4 s · gancho", p.get("title", "")),
                     ("4–12 s · idea 1", f"{p['slides'][0]['h']}. {p['slides'][0]['body']}" if p.get("slides") else ""),
                     ("12–20 s · idea 2", f"{p['slides'][1]['h']}. {p['slides'][1]['body']}" if p.get("slides") else ""),
                     ("20–25 s · dato", p.get("fact", "")),
                     ("25–30 s · cierre", p.get("cta", ""))]
            yy = cu.y
            for k, v in guion:
                d.text((x, yy), k, font=R.semi_font(20), fill="#888888")
                yy = texto(d, (x, yy + 28), v, 21, "#333333", ancho=PW - MG - x, lh=1.28) + 10
            cu.y = max(cu.y + 500, yy) + 30
            d.line((MG, cu.y - 20, PW - MG, cu.y - 20), fill="#E5E5E5", width=2)
        else:
            f = C.MEDIA / "stories" / f"{e['id']}.jpg"
            cu.sitio(420)
            d = cu.d
            d.text((MG, cu.y), f"{num}. Historia de pregunta · {fecha_txt(dt)}", font=R.semi_font(24), fill=R.ACENTO)
            cu.y += 44
            if f.exists():
                cu.pag.paste(ImageOps.fit(Image.open(f), (200, 356)), (MG, cu.y))
            p = posts.get(e["id"], {})
            texto(d, (MG + 230, cu.y), f"{p.get('title', '')}\n{p.get('caption', '')}", 22, "#333333", ancho=PW - 2 * MG - 230)
            cu.y += 356 + 40
            d.line((MG, cu.y - 20, PW - MG, cu.y - 20), fill="#E5E5E5", width=2)

    out = C.MEDIA / f"revision_{desde.isoformat()}_{hasta.isoformat()}.pdf"
    cu.paginas[0].save(out, "PDF", resolution=150, save_all=True, append_images=cu.paginas[1:])
    print(f"✓ {out} · {len(items)} publicaciones en {len(cu.paginas)} páginas")


if __name__ == "__main__":
    main()

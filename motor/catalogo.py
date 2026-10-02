"""Catálogo de plantillas con la marca del cliente: para enseñárselo y que elija.

Uso:  python catalogo.py --cliente demo [id_post]   → clientes/<id>/media/catalogo.jpg
Cada fila es una plantilla (portada, una diapositiva, el dato y la historia) con los colores, el logo y,
si las hay, las fotos del cliente. Sin fotos, las plantillas de foto muestran un hueco «Tu foto aquí».
"""
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

import biblioteca as B
import cliente as C
import plantillas as T
import render as R

NOMBRES = {"bloques": "Bloques de color", "tipografica": "Tipográfica", "foto_franja": "Foto con franja",
           "foto_completa": "Foto completa", "foto_marco": "Foto enmarcada"}


def _hueco():
    """Foto de relleno con los colores de marca, para clientes sin fotos todavía."""
    w, h = 1080, 1440
    im = Image.new("RGB", (w, h), R.mix(R.FONDO, R.PRINCIPAL, 0.35))
    d = ImageDraw.Draw(im)
    for i in range(0, w + h, 90):
        d.line((i, 0, i - h, h), fill=R.mix(R.FONDO, R.PRINCIPAL, 0.45), width=30)
    f = R.semi_font(64)
    t = "TU FOTO AQUÍ"
    d.text(((w - d.textlength(t, font=f)) / 2, h * 0.38), t, font=f, fill=R.FONDO)
    tmp = Path(tempfile.gettempdir()) / f"hueco_{C.ID}.jpg"
    im.save(tmp, quality=90)
    return {"id": "hueco", "archivo": str(tmp), "foco": {"x": 0.5, "y": 0.4}}


def main():
    posts = json.loads(R.POSTS.read_text(encoding="utf-8"))["posts"]
    if not [x for x in posts if not R.es_pregunta(x)] and (C.CONTENT / "muestras.json").exists():
        posts = json.loads((C.CONTENT / "muestras.json").read_text(encoding="utf-8"))["posts"]   # recién dado de alta
    pid = sys.argv[1] if len(sys.argv) > 1 else None
    p = next((x for x in posts if (x["id"] == pid if pid else not R.es_pregunta(x))), None)
    if not p:
        raise SystemExit("No hay ningún post con diapositivas para el catálogo.")
    lib = B.fotos()
    foto = lib[0] if lib else _hueco()
    if foto["id"] == "hueco":
        B.ruta = lambda f, _r=B.ruta: Path(f["archivo"]) if f.get("id") == "hueco" else _r(f)
    tw = 260
    filas = []
    for t in T.TODAS:
        f = foto if t in T.FOTO else None
        fs = [f] if f else []
        ims = [T.cover(t, p, f, "principal"), T.body(t, p, 1 if t != "foto_franja" else 2, fs, "mitad"), T.fact(t, p),
               T.story_fact(t, p, f)]
        ims = [i.resize((tw, int(i.height * tw / i.width))) for i in ims]
        fila = Image.new("RGB", (4 * (tw + 10) + 290, 470), "#FFFFFF")
        d = ImageDraw.Draw(fila)
        d.text((16, 30), NOMBRES[t], font=R.title_font(28), fill="#222222")
        d.text((16, 72), "con foto" if t in T.FOTO else "solo color", font=R.body_font(20), fill="#777777")
        d.text((16, 100), f'"{t}"', font=R.body_font(18), fill="#999999")
        for k, im in enumerate(ims):
            fila.paste(im, (290 + k * (tw + 10), 10))
        filas.append(fila)
    S = Image.new("RGB", (filas[0].width, sum(f.height for f in filas)), "#FFFFFF")
    y = 0
    for f in filas:
        S.paste(f, (0, y))
        y += f.height
    C.MEDIA.mkdir(parents=True, exist_ok=True)
    out = C.MEDIA / "catalogo.jpg"
    S.save(out, "JPEG", quality=88)
    print(f"✓ {out}")


if __name__ == "__main__":
    main()

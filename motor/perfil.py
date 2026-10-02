"""Simula la cuadrícula del perfil (3 columnas) con las portadas generadas, para revisar el mosaico.

Uso:  python perfil.py --cliente demo [n]     → clientes/<id>/media/perfil.jpg (las n primeras del feed, por defecto 12)
Instagram muestra la cuadrícula en 3:4; las portadas 4:5 y los reels 9:16 se recortan por el centro.
"""
import json
import sys

from PIL import Image, ImageDraw, ImageOps

import cliente as C
import render as R

CW, CH, GAP = 360, 480, 4


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    cal = json.loads(C.CAL.read_text(encoding="utf-8"))["posts"]
    feed = sorted((e for e in cal if e["type"] in ("carousel", "reel") and not e.get("skip")),
                  key=lambda e: e["publish_at"])[:n]
    feed.reverse()   # lo último publicado sale arriba a la izquierda
    filas = (len(feed) + 2) // 3
    S = Image.new("RGB", (3 * CW + 2 * GAP, filas * CH + (filas - 1) * GAP), "#FFFFFF")
    for i, e in enumerate(feed):
        f = (C.MEDIA / "carousels" / e["id"] / "01.jpg") if e["type"] == "carousel" else (C.MEDIA / "reels" / f"{e['id']}_cover.jpg")
        if not f.exists():
            if e["type"] == "reel":
                import reels
                f = reels.cover(e["id"])
            else:
                continue
        im = ImageOps.fit(Image.open(f).convert("RGB"), (CW, CH), Image.LANCZOS)
        if e["type"] == "reel":
            ImageDraw.Draw(im).polygon([(CW - 40, 18), (CW - 40, 42), (CW - 18, 30)], fill="#FFFFFF")
        S.paste(im, ((i % 3) * (CW + GAP), (i // 3) * (CH + GAP)))
    out = C.MEDIA / "perfil.jpg"
    S.save(out, "JPEG", quality=90)
    try:
        import plantillas as T
        dis = T._cargar_diseno()
        con = sum(1 for e in feed if dis.get(e["id"], {}).get("plantilla") in T.FOTO)
        print(f"✓ {out} · {con} de {len(feed)} con foto")
    except Exception:
        print(f"✓ {out}")


if __name__ == "__main__":
    main()

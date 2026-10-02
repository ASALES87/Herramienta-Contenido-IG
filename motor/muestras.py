"""Muestras para enseñar al cliente tras el alta, sin tocar su calendario ni sus posts.

Uso:  python muestras.py --cliente <id>   → clientes/<id>/media/muestras/
  portada_1..3.jpg   tres portadas con sus plantillas (y fotos, si ya hay)
  historia.jpg       la historia «¿Sabías que…?»
  pregunta.jpg       la historia de pregunta a la comunidad
  mosaico.jpg        cómo quedaría su perfil (9 casillas) con el nivel de fotos previsto
Los textos salen de content/muestras.json (los escribe alta.py a partir del cuestionario).
"""
import json

from PIL import Image, ImageOps

import cliente as C
import plantillas as T
import render as R

OUT = C.MEDIA / "muestras"


def main():
    datos = json.loads((C.CONTENT / "muestras.json").read_text(encoding="utf-8"))
    posts = [p for p in datos["posts"] if not R.es_pregunta(p)]
    pregunta = next((p for p in datos["posts"] if R.es_pregunta(p)), None)
    OUT.mkdir(parents=True, exist_ok=True)
    R.ensure_fonts()
    lst = T.elegidas()
    fotos_t = [t for t in lst if t in T.FOTO]
    color_t = [t for t in lst if t in T.COLOR] or ["bloques"]
    nv = (C.MARCA.get("fotos") or {}).get("nivel_max", "ninguna") if fotos_t else "ninguna"
    from biblioteca import fotos as _fotos
    lib = _fotos()
    hueco = None
    if fotos_t and not lib:
        import catalogo
        hueco = catalogo._hueco()
        import biblioteca as B
        B.ruta = lambda f, _r=B.ruta: __import__("pathlib").Path(f["archivo"]) if f.get("id") == "hueco" else _r(f)

    patron = T.PATRONES[nv]
    tonos = []
    portadas = []
    for i in range(9):
        p = posts[i % len(posts)]
        foto_slot = bool(fotos_t) and patron[i % len(patron)] == 1
        n_foto = sum(1 for k in range(i) if fotos_t and patron[k % len(patron)])
        t = fotos_t[n_foto % len(fotos_t)] if foto_slot else color_t[(i - n_foto) % len(color_t)]
        if nv == "ninguna":
            tono = R.SEQ_DEFAULT[i % 4]
        else:
            vec = {tonos[k] for k in (i - 1, i - 3) if k >= 0}
            pref = ["principal", "acento"] if foto_slot else ["fondo", "principal", "acento"]
            ops = [c for c in pref if c not in vec] or pref
            tono = ops[0]
        tonos.append(tono)
        foto = (lib[i % len(lib)] if lib else hueco) if foto_slot else None
        portadas.append(T.cover(t, p, foto, tono))
    for k in range(3):
        portadas[k].save(OUT / f"portada_{k + 1}.jpg", "JPEG", quality=90)
    t0, f0 = (fotos_t[0], (lib[0] if lib else hueco)) if fotos_t else (color_t[0], None)
    T.story_fact(t0, posts[0], f0).save(OUT / "historia.jpg", "JPEG", quality=90)
    if pregunta:
        R.story_question(pregunta).save(OUT / "pregunta.jpg", "JPEG", quality=90)
    cw, ch, gap = 360, 480, 4
    S = Image.new("RGB", (3 * cw + 2 * gap, 3 * ch + 2 * gap), "#FFFFFF")
    for i, im in enumerate(reversed(portadas)):
        S.paste(ImageOps.fit(im, (cw, ch), Image.LANCZOS), ((i % 3) * (cw + gap), (i // 3) * (ch + gap)))
    S.save(OUT / "mosaico.jpg", "JPEG", quality=90)
    print(f"✓ Muestras en {OUT} (nivel de fotos previsto: {nv})")


if __name__ == "__main__":
    main()

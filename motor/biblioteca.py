"""Biblioteca de fotos del cliente: propias (enviadas por el cliente) y de stock (Pexels / Pixabay).

clientes/<id>/biblioteca/
  index.json   {"fotos": [{"id", "archivo", "origen": "propia"|"stock", "notas", "chips", "foco": {"x","y"},
                           "credito", "query"}]}
  *.jpg        las fotos (las propias llegan con «Enviar foto»; las de stock las descarga este módulo)

clientes/<id>/content/fotos_asignadas.json   {post_id: [foto_id, …]}  → cada post usa siempre las mismas fotos.

Reglas al asignar (si el post no indica "foto"):
  1. propias antes que stock (si marca.contenido_propio.preferencia no es "stock");
  2. la que coincida con el pilar/las notas y menos se haya usado;
  3. no repetir una foto antes de DIAS_SIN_REPETIR días (por fecha de publicación del calendario);
  4. si no hay ninguna libre, el cliente admite stock (preferencia ≠ "propias") y hay clave de Pexels/Pixabay,
     se busca una de stock con post["foto_query"].
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import requests
from PIL import Image, ImageOps

import cliente as C

DIR = C.DIR / "biblioteca"
INDEX = DIR / "index.json"
ASIGNADAS = C.CONTENT / "fotos_asignadas.json"
DIAS_SIN_REPETIR = int((C.MARCA.get("biblioteca") or {}).get("dias_sin_repetir", 60))


def _load(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def fotos() -> list[dict]:
    return [f for f in _load(INDEX, {"fotos": []})["fotos"] if (DIR / f["archivo"]).exists()]


def por_id(fid: str) -> dict | None:
    return next((f for f in fotos() if f["id"] == fid), None)


def ruta(f: dict) -> Path:
    return DIR / f["archivo"]


def _fechas_calendario() -> dict:
    try:
        cal = json.loads(C.CAL.read_text(encoding="utf-8"))["posts"]
        return {e["id"]: datetime.fromisoformat(e["publish_at"]) for e in cal}
    except (OSError, ValueError, KeyError):
        return {}


def stock_permitido() -> bool:
    """Se pueden usar fotos de stock si el cliente no pidió solo las suyas y hay clave de Pexels o Pixabay."""
    pref = (C.MARCA.get("contenido_propio") or {}).get("preferencia", "mezcla")
    return pref != "propias" and bool(C.secreto("PEXELS_API_KEY") or C.secreto("PIXABAY_API_KEY"))


def _asignadas() -> dict:
    a = _load(ASIGNADAS, {})
    return {k: (v if isinstance(v, list) else [v]) for k, v in a.items()}


def libres(fecha: datetime | None = None) -> list[dict]:
    """Fotos que se pueden usar en esa fecha (no usadas en ±DIAS_SIN_REPETIR días)."""
    fecha = fecha or datetime.now()
    fechas = _fechas_calendario()
    usadas = {}
    for pid, ids in _asignadas().items():
        for fid in ids:
            usadas.setdefault(fid, []).append(fechas.get(pid))
    return [f for f in fotos()
            if not any(d and abs((d - fecha).days) < DIAS_SIN_REPETIR for d in usadas.get(f["id"], []))]


def asignar_varias(post: dict, n: int = 1) -> list[dict]:
    """Hasta n fotos distintas para un post (la 1.ª para la portada). La elección se guarda y no cambia."""
    if post.get("foto"):
        f = por_id(post["foto"])
        return [f] if f else []
    asig = _asignadas()
    ya = [f for f in (por_id(x) for x in asig.get(post["id"], [])) if f]
    if len(ya) >= n:
        return ya[:n]
    pref = (C.MARCA.get("contenido_propio") or {}).get("preferencia", "mezcla")
    fechas = _fechas_calendario()
    uso_total = {}
    for ids in asig.values():
        for fid in ids:
            uso_total[fid] = uso_total.get(fid, 0) + 1
    q = (post.get("foto_query") or post.get("video_query") or "").lower().split()
    candidatas = []
    for f in libres(fechas.get(post["id"], datetime.now())):
        if f in ya:
            continue
        texto = " ".join([f.get("notas", ""), " ".join(f.get("chips", [])), f.get("query", "")]).lower()
        afin = sum(1 for w in q if w in texto)
        propia = f.get("origen") == "propia"
        if pref == "propias" and not propia:
            continue
        orden = (0 if (propia and pref != "stock") or (not propia and pref == "stock") else 1, -afin, uso_total.get(f["id"], 0))
        candidatas.append((orden, f))
    candidatas.sort(key=lambda x: x[0])
    elegidas = ya + [f for _, f in candidatas][: n - len(ya)]
    while len(elegidas) < n and stock_permitido():
        qq = post.get("foto_query") or post.get("video_query") or C.MARCA.get("video_query_defecto")
        f = stock(qq) if qq else None
        if not f:
            break
        elegidas.append(f)
    if elegidas and [f["id"] for f in elegidas] != asig.get(post["id"]):
        asig[post["id"]] = [f["id"] for f in elegidas]
        _save(ASIGNADAS, asig)
    return elegidas


def asignar(post: dict) -> dict | None:
    r = asignar_varias(post, 1)
    return r[0] if r else None


# ---------- stock (gratis con clave): Pexels primero, luego Pixabay ----------

def _alta(archivo: Path, origen: str, credito: str, query: str) -> dict:
    idx = _load(INDEX, {"fotos": []})
    n = len(idx["fotos"]) + 1
    f = {"id": f"{'s' if origen == 'stock' else 'p'}{n:03d}", "archivo": archivo.name, "origen": origen,
         "notas": "", "chips": [], "foco": {"x": 0.5, "y": 0.45}, "credito": credito, "query": query}
    idx["fotos"].append(f)
    _save(INDEX, idx)
    return f


def stock(query: str) -> dict | None:
    usados = {f.get("credito") for f in fotos()}
    for buscar in (_pexels, _pixabay):
        try:
            r = buscar(query, usados)
        except requests.RequestException as e:
            print(f"  (aviso) búsqueda de foto de stock fallida: {e}")
            r = None
        if r:
            url, credito = r
            DIR.mkdir(parents=True, exist_ok=True)
            dest = DIR / f"stock_{abs(hash(credito)) % 10**8}.jpg"
            with requests.get(url, timeout=120) as dl:
                dl.raise_for_status()
                dest.write_bytes(dl.content)
            print(f"  ↓ Foto de stock: {credito}")
            return _alta(dest, "stock", credito, query)
    return None


def _pexels(query, usados):
    key = C.secreto("PEXELS_API_KEY")
    if not key:
        return None
    r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
                     params={"query": query, "orientation": "portrait", "per_page": 15}, timeout=30)
    r.raise_for_status()
    for ph in r.json().get("photos", []):
        cred = f"Pexels: {ph.get('url')} · {ph.get('photographer')}"
        if cred not in usados:
            return ph["src"].get("large2x") or ph["src"]["original"], cred
    return None


def _pixabay(query, usados):
    key = C.secreto("PIXABAY_API_KEY")
    if not key:
        return None
    r = requests.get("https://pixabay.com/api/", params={"key": key, "q": query, "image_type": "photo",
                     "orientation": "vertical", "safesearch": "true", "per_page": 20}, timeout=30)
    r.raise_for_status()
    for h in r.json().get("hits", []):
        cred = f"Pixabay: {h.get('pageURL')} · {h.get('user')}"
        if cred not in usados:
            return h["largeImageURL"], cred
    return None


# ---------- recorte ----------
_cache = {}


def recorte(f: dict, w: int, h: int, dy: float = 0.0) -> Image.Image:
    """Recorta la foto al tamaño pedido respetando su punto de interés (foco). dy desplaza el foco en vertical."""
    p = ruta(f)
    if p not in _cache:
        _cache[p] = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
    foco = f.get("foco") or {}
    cx = min(1, max(0, float(foco.get("x", 0.5))))
    cy = min(1, max(0, float(foco.get("y", 0.45)) + dy))
    return ImageOps.fit(_cache[p], (w, h), Image.LANCZOS, centering=(cx, cy))


# ---------- línea de comandos ----------
# python biblioteca.py --cliente demo lista
# python biblioteca.py --cliente demo añadir foto1.jpg foto2.jpg --notas "hogaza recién hecha" --chips producto
def main():
    import argparse
    import shutil
    ap = argparse.ArgumentParser(description="Biblioteca de fotos del cliente")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lista")
    a = sub.add_parser("añadir")
    a.add_argument("archivos", nargs="+")
    a.add_argument("--notas", default="")
    a.add_argument("--chips", nargs="*", default=[])
    a.add_argument("--origen", default="propia", choices=["propia", "stock"])
    a.add_argument("--credito", default="")
    args = ap.parse_args()
    if args.cmd == "lista":
        for f in fotos():
            print(f"{f['id']}  {f['origen']:7} {f['archivo']:30} {f.get('notas', '')[:50]}")
        print(f"{len(fotos())} fotos en {DIR}")
        return
    DIR.mkdir(parents=True, exist_ok=True)
    for src in args.archivos:
        src = Path(src)
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        if max(im.size) > 2160:   # lado largo 2160 px, como la página «Enviar foto»
            im.thumbnail((2160, 2160), Image.LANCZOS)
        dest = DIR / f"{datetime.now().strftime('%Y%m%d')}_{src.stem}.jpg"
        im.save(dest, "JPEG", quality=90)
        f = _alta(dest, args.origen, args.credito, "")
        idx = _load(INDEX, {"fotos": []})
        for x in idx["fotos"]:
            if x["id"] == f["id"]:
                x["notas"], x["chips"] = args.notas, args.chips
        _save(INDEX, idx)
        print(f"✓ {f['id']} ← {src.name}")


if __name__ == "__main__":
    main()

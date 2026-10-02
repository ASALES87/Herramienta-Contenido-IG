"""Avisos urgentes del cliente («Hoy cerramos a las 14:00», «Ya ha llegado el roscón»): una historia con su marca
que sale el mismo día, fuera de las tandas (no espera aprobación: es el texto del propio cliente).

Uso:
  python motor/avisos.py --cliente <id> previa  --texto "…" [--foto F]             → media/avisos/previa.jpg
  python motor/avisos.py --cliente <id> crear   --texto "…" [--foto F] [--cuando ahora|HH:MM|AAAA-MM-DDTHH:MM]
  python motor/avisos.py --cliente <id> cancelar <id-aviso>
  python motor/avisos.py --cliente <id> lista

Se guardan en content/avisos.json (imagen en content/avisos/, que sí va a git) y entran en el calendario como
historia («aviso»: true). Saldrá en la siguiente
pasada de publicación a partir de su hora (las pasadas van a las horas de publicación de los clientes).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageOps

import cliente as C
import render as R

AVISOS = C.CONTENT / "avisos.json"
CARPETA = C.MEDIA / "avisos"
MAX = 140
MESES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MADRID = ZoneInfo("Europe/Madrid")   # el calendario va en hora de Madrid


def ahora() -> datetime:
    return datetime.now(MADRID).replace(tzinfo=None, second=0, microsecond=0)


def _load(p, d):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return d


def _save(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def imagen(texto: str, foto: Path | None = None) -> Image.Image:
    """Historia 1080x1920. Con foto: la foto de fondo con un velo y el aviso en una tarjeta; sin foto: color de marca."""
    R.ensure_fonts()
    W, SH, M = R.W, R.SH, R.M
    if foto:
        img = ImageOps.fit(ImageOps.exif_transpose(Image.open(foto)).convert("RGB"), (W, SH), Image.LANCZOS, centering=(0.5, 0.45))
        velo = Image.new("RGB", (W, SH), R.OSCURO)
        img = Image.blend(img, velo, 0.30)
    else:
        img = Image.new("RGB", (W, SH), R.PRINCIPAL)
    d = ImageDraw.Draw(img)
    on_card = R.legible(R.FONDO, R.TEXTO, R.OSCURO)
    hoy = ahora()
    chip_txt = f'{(C.MARCA.get("textos") or {}).get("aviso", "Aviso")} · {hoy.day} {MESES[hoy.month]}'
    # tarjeta con el texto del cliente: centrada sin foto; con foto, abajo para que se vea la foto
    tf, tl, tlh = R.fit_text(d, texto, R.title_font, W - 2 * M - 120, 620, 96, 52, 1.14)
    card_h = tlh * len(tl) + 220
    cy = (SH - card_h) // 2 - 40 if not foto else SH - 380 - card_h
    d.rounded_rectangle((M, cy, W - M, cy + card_h), radius=48, fill=R.FONDO)
    R.chip(d, M + 60, cy + 56, chip_txt.upper(), R.ACENTO, R.legible(R.ACENTO, R.OSCURO, R.FONDO), size=30)
    R.draw_lines(d, (M + 60, cy + 150), tl, tf, tlh, on_card)
    sobre = R.legible(R.PRINCIPAL, R.FONDO, "#FFFFFF") if not foto else "#FFFFFF"
    R.wordmark(img, 0, SH - 300, sobre, R.ACENTO, R.legible(R.ACENTO, R.OSCURO, R.FONDO), size=44, center=True)
    return img


def _cuando(v: str | None) -> datetime:
    ya = ahora()
    if not v or v == "ahora":
        return ya
    if len(v) == 5:   # HH:MM de hoy (si ya ha pasado, ahora)
        h, m = map(int, v.split(":"))
        t = ya.replace(hour=h, minute=m)
        return t if t >= ya else ya
    return max(ya, datetime.fromisoformat(v))


def crear(texto: str, foto: Path | None, cuando: str | None, origen: str = "app") -> dict:
    texto = " ".join(texto.split())[:MAX]
    if not texto:
        raise SystemExit("El aviso no tiene texto.")
    t = _cuando(cuando)
    avisos = _load(AVISOS, {"avisos": []})
    n = 1 + sum(1 for a in avisos["avisos"] if a["id"].startswith(f"av-{t:%y%m%d}"))
    aid = f"av-{t:%y%m%d}-{n}"
    # la imagen va en content/avisos/ (sí se sube a git) para que GitHub Actions la tenga al publicar
    (C.CONTENT / "avisos").mkdir(parents=True, exist_ok=True)
    rel = f"../content/avisos/{aid}.jpg"
    imagen(texto, foto).save(C.CONTENT / "avisos" / f"{aid}.jpg", "JPEG", quality=88, optimize=True, progressive=True)
    a = {"id": aid, "texto": texto, "publish_at": t.strftime("%Y-%m-%dT%H:%M"), "creado": ahora().isoformat(timespec="minutes"),
         "foto": str(foto.name) if foto else None, "origen": origen, "estado": "programado"}
    avisos["avisos"].append(a)
    _save(AVISOS, avisos)
    cal = _load(C.CAL, {"posts": []})
    cal["posts"].append({"id": aid, "type": "story", "publish_at": a["publish_at"], "files": [rel], "title": texto, "aviso": True})
    cal["posts"].sort(key=lambda e: e["publish_at"])
    _save(C.CAL, cal)
    return a


def cancelar(aid: str) -> None:
    avisos = _load(AVISOS, {"avisos": []})
    pub = _load(C.PUBLISHED, {})
    if aid in pub:
        raise SystemExit("Ese aviso ya se ha publicado.")
    for a in avisos["avisos"]:
        if a["id"] == aid:
            a["estado"] = "cancelado"
    _save(AVISOS, avisos)
    cal = _load(C.CAL, {"posts": []})
    cal["posts"] = [e for e in cal["posts"] if e["id"] != aid]
    _save(C.CAL, cal)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("previa", "crear"):
        s = sub.add_parser(n)
        s.add_argument("--texto", required=True)
        s.add_argument("--foto")
        if n == "crear":
            s.add_argument("--cuando")
            s.add_argument("--origen", default="app")
    s = sub.add_parser("cancelar"); s.add_argument("id")
    sub.add_parser("lista")
    a = ap.parse_args()
    foto = Path(a.foto) if getattr(a, "foto", None) else None
    if a.cmd == "previa":
        CARPETA.mkdir(parents=True, exist_ok=True)
        f = CARPETA / "previa.jpg"
        imagen(" ".join(a.texto.split())[:MAX], foto).save(f, "JPEG", quality=88)
        print(f"✓ {f}")
    elif a.cmd == "crear":
        x = crear(a.texto, foto, a.cuando, a.origen)
        print(f"✓ Aviso {x['id']} programado para {x['publish_at'].replace('T', ' a las ')}")
    elif a.cmd == "cancelar":
        cancelar(a.id)
        print(f"✓ Aviso {a.id} cancelado")
    else:
        pub = _load(C.PUBLISHED, {})
        for x in _load(AVISOS, {"avisos": []})["avisos"]:
            print(f"{x['id']:14} {x['publish_at']}  {'publicado' if x['id'] in pub else x['estado']:10} {x['texto'][:60]}")


if __name__ == "__main__":
    main()

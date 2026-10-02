"""Ejecuta un comando del motor para todos los clientes (lo usan los workflows de GitHub).

Uso:
  python motor/todos.py publicar [--simular] [--cliente <id>]   publica lo que toca (máx. 1 por cliente y pasada)
  python motor/todos.py siguiente --cliente <id>                 publica YA la siguiente de un cliente (prueba)
  python motor/todos.py hay-reels                                 «si» si algún cliente tiene un reel a punto (para instalar ffmpeg)
  python motor/todos.py diario --dir CARPETA [--informe]          comentarios y métricas de cada cliente → CARPETA/<id>_*.md
  python motor/todos.py horarios [--escribir]                     horas de publicación de los clientes → cron de publicar.yml

Clientes: los activos; con --simular, también los de ensayo. Los secretos llegan en SECRETOS (toJSON(secrets)) y
se pasan a cada cliente con su sufijo (IG_ACCESS_TOKEN_<CLIENTE>…), sin que un cliente vea los de otro.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CLIENTES = ROOT / "clientes"
MOTOR = ROOT / "motor"
MADRID = ZoneInfo("Europe/Madrid")
COMUNES = ("IG_APP_ID", "IG_APP_SECRET", "PEXELS_API_KEY", "PIXABAY_API_KEY", "R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID",
           "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_URL", "MEDIA_HOST")


def _load(p, d):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return d


def clientes(ensayo=False, solo=None):
    for d in sorted(CLIENTES.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or not (d / "marca.json").exists():
            continue
        if solo and d.name != solo:
            continue
        plan = _load(d / "content" / "plan.json", {})
        if _load(d / "marca.json", {}).get("solo_referencia"):
            continue   # cliente de referencia: nunca se toca desde aquí
        if plan.get("activo") or (ensayo and plan.get("ensayo")) or solo:
            yield d.name, plan


POR_CLIENTE = ("IG_ACCESS_TOKEN_", "IG_USER_ID_", "IG_TOKEN_EXPIRES_")


def entorno(cid: str) -> dict:
    """Variables para el proceso de un cliente: las suyas (con sufijo) y las comunes; nunca las de otro cliente."""
    suf = "_" + cid.upper().replace("-", "_")
    env = {k: v for k, v in os.environ.items()
           if k != "SECRETOS" and not (k.startswith(POR_CLIENTE) and not k.endswith(suf))}
    try:   # compatibilidad: secretos en bloque (ya no se usa en los workflows)
        sec = json.loads(os.environ.get("SECRETOS") or "{}")
    except ValueError:
        sec = {}
    for k, v in sec.items():
        if k.endswith(suf) or k in COMUNES:
            env[k] = v
    env["CLIENTE"] = cid
    return env


def run(cid, script, *args, check=False):
    r = subprocess.run([sys.executable, str(MOTOR / script), "--cliente", cid, *args], env=entorno(cid),
                       capture_output=True, text=True)
    salida = (r.stdout + r.stderr).strip()
    if salida:
        print("\n".join(f"  [{cid}] {l}" for l in salida.splitlines()))
    if check and r.returncode != 0:
        raise RuntimeError(f"{script} falló para {cid}")
    return r.returncode


def cmd_publicar(a):
    fallos = 0
    for cid, _ in clientes(ensayo=a.simular, solo=a.cliente):
        print(f"→ {cid}")
        run(cid, "render.py")
        fallos += run(cid, "publish.py", "run", "--max", "1", *(["--dry-run"] if a.simular else [])) != 0
    if fallos:
        sys.exit(f"{fallos} cliente(s) con errores al publicar")


def cmd_siguiente(a):
    run(a.cliente, "render.py")
    sys.exit(run(a.cliente, "publish.py", "next"))


def cmd_hay_reels(a):
    ahora = datetime.now(MADRID).replace(tzinfo=None)
    for cid, _ in clientes(ensayo=True):
        cal = _load(CLIENTES / cid / "content" / "content_calendar.json", {"posts": []})["posts"]
        pub = _load(CLIENTES / cid / "content" / "published.json", {})
        for e in cal:
            if e["type"] == "reel" and e["id"] not in pub and datetime.fromisoformat(e["publish_at"]) <= ahora + timedelta(minutes=40):
                print("si")
                return
    print("no")


def cmd_diario(a):
    out = Path(a.dir)
    out.mkdir(parents=True, exist_ok=True)
    for cid, _ in clientes():
        run(cid, "comentarios.py", "--out", str(out / f"{cid}_comentarios.md"))
        run(cid, "metricas.py", *(["--informe", str(out / f"{cid}_informe.md")] if a.informe else []))


# ---------- horarios: cron de publicar.yml según las horas de los clientes ----------
WF = ROOT / ".github" / "workflows" / "publicar.yml"


def horas_madrid() -> list[str]:
    hs = set()
    for cid, plan in clientes(ensayo=True):
        for k in ("carrusel", "dato", "pregunta", "tu_turno", "reels"):
            h = (plan.get(k) or {}).get("hora")
            if h:
                hs.add(h)
    return sorted(hs) or ["08:00", "13:30"]


def cron_lines(horas):
    """Cada hora de Madrid → una línea cron en UTC con las dos horas posibles (verano UTC+2 / invierno UTC+1).
    Se lanza 5 min después; publish.py solo publica lo que ya ha llegado a su hora y no repite nada."""
    lines = []
    for h in horas:
        hh, mm = map(int, h.split(":"))
        m = (mm + 5) % 60
        extra = (mm + 5) // 60
        lines.append(f'    - cron: "{m} {(hh - 2 + extra) % 24},{(hh - 1 + extra) % 24} * * *"   # {h} Madrid')
    return lines


def cmd_horarios(a):
    hs = horas_madrid()
    bloque = "\n".join(cron_lines(hs))
    print(f"Horas de publicación (Madrid): {', '.join(hs)}")
    print(bloque)
    if a.escribir:
        if not WF.exists():
            sys.exit(f"No existe {WF}")
        txt = WF.read_text(encoding="utf-8")
        nuevo = re.sub(r"(# >>> horarios[^\n]*\n).*?(\n\s*# <<< horarios)", lambda m: m.group(1) + bloque + m.group(2), txt, flags=re.S)
        if nuevo != txt:
            WF.write_text(nuevo, encoding="utf-8")
            print("✓ publicar.yml actualizado (súbelo a GitHub)")
        else:
            print("publicar.yml ya estaba al día")


# ---------- secretos: cada workflow nombra uno a uno los secretos de cada cliente ----------
# (GitHub marca como sospechoso pasar todos los secretos de golpe con toJSON(secrets))
WORKFLOWS = ROOT / ".github" / "workflows"


def todos_los_clientes():
    for d in sorted(CLIENTES.iterdir()):
        if d.is_dir() and not d.name.startswith("_") and (d / "marca.json").exists() \
                and not _load(d / "marca.json", {}).get("solo_referencia"):
            yield d.name


def lineas_secretos(indent: str) -> list[str]:
    L = [f"{indent}{k}: ${{{{ secrets.{k} }}}}" for k in COMUNES if k != "MEDIA_HOST"]
    for cid in todos_los_clientes():
        suf = cid.upper().replace("-", "_")
        for k in ("IG_ACCESS_TOKEN", "IG_USER_ID"):
            L.append(f"{indent}{k}_{suf}: ${{{{ secrets.{k}_{suf} }}}}")
    return L


def cmd_secretos(a):
    carpeta = Path(a.dir) if a.dir else WORKFLOWS
    cambios = 0
    for wf in sorted(carpeta.glob("*.yml")):
        txt = wf.read_text(encoding="utf-8")
        out, pos = [], 0
        for m in re.finditer(r"^([ ]*)# >>> secretos[^\n]*\n(.*?)^([ ]*)# <<< secretos", txt, flags=re.S | re.M):
            indent = m.group(1)
            out.append(txt[pos:m.start(2)] + "\n".join(lineas_secretos(indent)) + "\n")
            pos = m.start(3)
        out.append(txt[pos:])
        nuevo = "".join(out)
        if nuevo != txt:
            wf.write_text(nuevo, encoding="utf-8")
            cambios += 1
            print(f"✓ {wf.name}: secretos de {len(list(todos_los_clientes()))} clientes")
    print("Workflows al día." if not cambios else f"{cambios} workflow(s) actualizados (súbelos a GitHub)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("publicar"); s.add_argument("--simular", action="store_true"); s.add_argument("--cliente"); s.set_defaults(fn=cmd_publicar)
    s = sub.add_parser("siguiente"); s.add_argument("--cliente", required=True); s.set_defaults(fn=cmd_siguiente)
    sub.add_parser("hay-reels").set_defaults(fn=cmd_hay_reels)
    s = sub.add_parser("diario"); s.add_argument("--dir", required=True); s.add_argument("--informe", action="store_true"); s.set_defaults(fn=cmd_diario)
    s = sub.add_parser("horarios"); s.add_argument("--escribir", action="store_true"); s.set_defaults(fn=cmd_horarios)
    s = sub.add_parser("secretos", help="actualiza la lista de secretos por cliente en los workflows")
    s.add_argument("--escribir", action="store_true"); s.add_argument("--dir"); s.set_defaults(fn=cmd_secretos)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

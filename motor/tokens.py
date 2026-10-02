"""Tokens: renovación automática del token de Instagram de cada cliente y aviso del GH_PAT de GitHub.

El token de Instagram (inicio de sesión de Instagram) dura 60 días y se puede renovar si tiene más de 24 h.
Se renueva cuando le quedan RENOVAR_A_DIAS o menos (o si no se sabe cuándo caduca). La fecha de caducidad
se guarda en clientes/<id>/content/token.json (no es secreta); el token nuevo va a los Secrets de GitHub.

El GH_PAT (token de GitHub con permiso para guardar Secrets) NO se puede renovar por programa: se avisa con
30, 14, 7, 3 y 1 días de margen. Su caducidad va en la variable de GitHub GH_PAT_CADUCA (AAAA-MM-DD).

Uso:
  python motor/tokens.py estado                         caducidad del token de cada cliente
  python motor/tokens.py renovar-todos --dir CARPETA    renueva los que toquen; deja cada token en CARPETA/IG_ACCESS_TOKEN_<SUFIJO>
  python motor/tokens.py aviso-pat [--out aviso.md]     comprueba la caducidad del GH_PAT
Los tokens se leen de las variables IG_ACCESS_TOKEN_<SUFIJO> o, en GitHub Actions, de SECRETOS (toJSON(secrets)).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CLIENTES = ROOT / "clientes"
RENOVAR_A_DIAS = 20
AVISOS_PAT = {30, 14, 7, 3, 2, 1, 0}


def _secretos() -> dict:
    s = dict(os.environ)
    try:
        s.update(json.loads(os.environ.get("SECRETOS") or "{}"))
    except ValueError:
        pass
    return s


def _clientes():
    for d in sorted(CLIENTES.iterdir()):
        if d.is_dir() and not d.name.startswith("_") and (d / "marca.json").exists():
            try:
                plan = json.loads((d / "content" / "plan.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                plan = {}
            yield d.name, d, plan


def sufijo(cid: str) -> str:
    return cid.upper().replace("-", "_")


def _info(d: Path) -> dict:
    try:
        return json.loads((d / "content" / "token.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def cmd_estado(a):
    sec = _secretos()
    for cid, d, plan in _clientes():
        tiene = bool(sec.get(f"IG_ACCESS_TOKEN_{sufijo(cid)}"))
        cad = _info(d).get("caduca")
        dias = (date.fromisoformat(cad) - date.today()).days if cad else None
        estado = "sin token" if not tiene and not cad else (f"caduca el {cad} ({dias} días)" if cad else "caducidad desconocida")
        tipo = "activo" if plan.get("activo") else "ensayo" if plan.get("ensayo") else "inactivo"
        print(f"{cid:24} {tipo:8} {estado}")


def cmd_renovar_todos(a):
    sec = _secretos()
    out = Path(a.dir)
    out.mkdir(parents=True, exist_ok=True)
    fallos = []
    for cid, d, plan in _clientes():
        tok = sec.get(f"IG_ACCESS_TOKEN_{sufijo(cid)}")
        if not tok:
            continue
        cad = _info(d).get("caduca")
        if cad and (date.fromisoformat(cad) - date.today()).days > RENOVAR_A_DIAS and not a.forzar:
            print(f"{cid}: no toca (caduca el {cad})")
            continue
        try:
            r = requests.get("https://graph.instagram.com/refresh_access_token",
                             params={"grant_type": "ig_refresh_token", "access_token": tok}, timeout=60)
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            data = {"error": {"message": f"sin conexión con Instagram ({type(e).__name__})"}}
        if "access_token" not in data:
            err = (data.get("error") or {}).get("message", str(data))[:200]
            print(f"✗ {cid}: no se pudo renovar ({err})")
            fallos.append(f"- **{cid}**: {err}")
            continue
        nueva = date.today() + timedelta(seconds=int(data.get("expires_in", 0)))
        (out / f"IG_ACCESS_TOKEN_{sufijo(cid)}").write_text(data["access_token"], encoding="utf-8")
        (d / "content" / "token.json").write_text(json.dumps({"caduca": nueva.isoformat(), "renovado": date.today().isoformat()},
                                                             indent=1) + "\n", encoding="utf-8")
        print(f"✓ {cid}: renovado, caduca el {nueva}")
    if fallos:
        (out / "fallos.md").write_text("No se pudo renovar el token de Instagram de:\n\n" + "\n".join(fallos) +
                                       "\n\nSi el token ya caducó, hay que generar uno nuevo con el cliente (videollamada).\n",
                                       encoding="utf-8")


def cmd_aviso_pat(a):
    cad = os.environ.get("GH_PAT_CADUCA") or _secretos().get("GH_PAT_CADUCA")
    if not cad:
        msg = "No está configurada la variable GH_PAT_CADUCA: no puedo avisar de cuándo caduca el GH_PAT."
    else:
        dias = (date.fromisoformat(cad) - date.today()).days
        if dias not in AVISOS_PAT and dias > 0:
            print(f"GH_PAT caduca el {cad} ({dias} días): sin aviso hoy.")
            return
        msg = (f"El GH_PAT caduca el {cad} ({'ya ha caducado' if dias < 0 else f'quedan {dias} días'}).\n\n"
               "Sin él no se pueden guardar los tokens renovados de Instagram. Pasos:\n"
               "1. GitHub → Settings → Developer settings → Fine-grained tokens → Regenerate (mismo permiso: Secrets read/write en este repo).\n"
               "2. `gh secret set GH_PAT` con el token nuevo.\n"
               "3. Actualiza la variable `GH_PAT_CADUCA` con la nueva fecha.")
    print(msg)
    if a.out:
        Path(a.out).write_text(msg + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("estado").set_defaults(fn=cmd_estado)
    s = sub.add_parser("renovar-todos"); s.add_argument("--dir", required=True); s.add_argument("--forzar", action="store_true")
    s.set_defaults(fn=cmd_renovar_todos)
    s = sub.add_parser("aviso-pat"); s.add_argument("--out"); s.set_defaults(fn=cmd_aviso_pat)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

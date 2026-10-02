"""Tandas de contenido de todos los clientes: cuándo toca escribir, cerrar una tanda y aprobarla.

Uso (desde la carpeta del repo; no lleva --cliente salvo donde se indica):
  python motor/tandas.py estado [--json]          días de contenido que le quedan a cada cliente y quién necesita tanda
  python motor/tandas.py cerrar --cliente <id>    tras escribir los posts: planifica, renderiza, genera el cuaderno
                                                  de revisión y registra la tanda (pendiente o aprobada)
  python motor/tandas.py aprobar --cliente <id> [<tanda>]   el cliente la ha aprobado
  python motor/tandas.py vencidas                 aprueba las tandas pendientes con más de PLAZO días (lo que no se
                                                  comenta en 3 días se publica tal cual)
  python motor/tandas.py avisos --out avisos.md   texto para el aviso de GitHub si a alguien se le acaba el contenido

Qué clientes cuentan: los activos (plan.json → "activo": true) y los de ensayo ("ensayo": true).
Registro de cada cliente en content/tandas.json:
  {"t2611": {"estado": "pendiente"|"aprobada", "creada": fecha, "aprobada": fecha, "desde", "hasta", "posts": [ids], "pdf"}}
Mientras una tanda está pendiente, publish.py no publica nada de ella (ver content_calendar.bloqueados()).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTES = ROOT / "clientes"
PLAZO = 3   # días para revisar una tanda antes de que se apruebe sola


def _load(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def clientes(todos=False):
    for d in sorted(CLIENTES.iterdir()):
        if d.is_dir() and not d.name.startswith("_") and (d / "marca.json").exists():
            plan = _load(d / "content" / "plan.json", {})
            if todos or plan.get("activo") or plan.get("ensayo"):
                yield d.name, d, plan


def estado_cliente(cid, d, plan, hoy=None):
    hoy = hoy or date.today()
    cal = _load(d / "content" / "content_calendar.json", {"posts": []})["posts"]
    posts = _load(d / "content" / "posts.json", {"posts": []})["posts"]
    programados = {e["id"] for e in cal}
    fin = max((datetime.fromisoformat(e["publish_at"]).date() for e in cal), default=None)
    quedan = (fin - hoy).days if fin else 0
    minimo = (plan.get("tanda") or {}).get("dias_minimos_por_delante", 21)
    tandas = _load(d / "content" / "tandas.json", {})
    pendientes = [t for t, v in tandas.items() if v.get("estado") == "pendiente"]
    sin_programar = [p["id"] for p in posts if p["id"] not in programados]
    return {"cliente": cid, "activo": bool(plan.get("activo")), "ensayo": bool(plan.get("ensayo")),
            "contenido_hasta": fin.isoformat() if fin else None, "dias_quedan": max(0, quedan), "minimo": minimo,
            "necesita_tanda": quedan < minimo and not pendientes and not sin_programar,
            "posts_sin_programar": len(sin_programar), "tandas_pendientes": pendientes,
            "dias_por_tanda": (plan.get("tanda") or {}).get("dias_por_tanda", 35),
            "aprobacion": plan.get("aprobacion", "primera"), "guia": f"clientes/{cid}/content/GUIA_TANDAS.md"}


def cmd_estado(a):
    hoy = date.fromisoformat(a.hoy) if a.hoy else None
    filas = [estado_cliente(c, d, p, hoy) for c, d, p in clientes()]
    if a.json:
        print(json.dumps(filas, ensure_ascii=False, indent=1))
        return
    if not filas:
        print("No hay clientes activos ni de ensayo.")
    for f in filas:
        marca = "ACTIVO" if f["activo"] else "ensayo"
        aviso = "→ NECESITA TANDA" if f["necesita_tanda"] else ""
        pend = f" · tanda pendiente de aprobar: {', '.join(f['tandas_pendientes'])}" if f["tandas_pendientes"] else ""
        sin = f" · {f['posts_sin_programar']} posts escritos sin programar" if f["posts_sin_programar"] else ""
        print(f"{f['cliente']:24} {marca:6} contenido hasta {f['contenido_hasta'] or '—'} ({f['dias_quedan']} días, "
              f"mínimo {f['minimo']}){pend}{sin} {aviso}")


def _run(cid, *args):
    r = subprocess.run([sys.executable, str(ROOT / "motor" / args[0]), "--cliente", cid, *args[1:]],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"✗ {args[0]} falló para {cid}:\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
    return r.stdout


def cmd_cerrar(a):
    d = CLIENTES / a.cliente
    plan = _load(d / "content" / "plan.json", {})
    antes = {e["id"] for e in _load(d / "content" / "content_calendar.json", {"posts": []})["posts"]}
    print(_run(a.cliente, "planificar.py").strip())
    cal = _load(d / "content" / "content_calendar.json", {"posts": []})["posts"]
    nuevas = [e for e in cal if e["id"] not in antes]
    if not nuevas:
        raise SystemExit("No hay publicaciones nuevas: escribe primero los posts en posts.json.")
    desde = min(e["publish_at"][:10] for e in nuevas)
    hasta = max(e["publish_at"][:10] for e in nuevas)
    _run(a.cliente, "render.py")
    _run(a.cliente, "perfil.py", "15")
    pdf = _run(a.cliente, "revision.py", "--desde", desde, "--hasta", hasta).strip().split("✓ ")[-1].split(" · ")[0]
    tandas = _load(d / "content" / "tandas.json", {})
    tid = a.tanda or f"t{desde[2:4]}{desde[5:7]}"
    while tid in tandas:
        tid += "b"
    aprob = plan.get("aprobacion", "primera")
    necesita = aprob == "cada" or (aprob == "primera" and not any(v.get("estado") == "aprobada" for v in tandas.values()))
    ids = sorted({e["id"] for e in nuevas})
    tandas[tid] = {"estado": "pendiente" if necesita else "aprobada", "creada": date.today().isoformat(),
                   "aprobada": None if necesita else date.today().isoformat(), "desde": desde, "hasta": hasta,
                   "posts": ids, "pdf": str(Path(pdf).relative_to(ROOT)) if pdf.startswith(str(ROOT)) else pdf}
    _save(d / "content" / "tandas.json", tandas)
    print(f"✓ Tanda {tid} de {a.cliente}: {len(ids)} publicaciones del {desde} al {hasta} · "
          f"{'PENDIENTE de aprobación (se aprueba sola en ' + str(PLAZO) + ' días)' if necesita else 'aprobada'}")
    print(f"  Cuaderno para el cliente: {tandas[tid]['pdf']}")


def cmd_aprobar(a):
    p = CLIENTES / a.cliente / "content" / "tandas.json"
    tandas = _load(p, {})
    objetivo = [a.tanda] if a.tanda else [t for t, v in tandas.items() if v.get("estado") == "pendiente"]
    for t in objetivo:
        if t not in tandas:
            raise SystemExit(f"No existe la tanda {t}")
        tandas[t].update(estado="aprobada", aprobada=date.today().isoformat())
        print(f"✓ {a.cliente}: tanda {t} aprobada")
    _save(p, tandas)


def cmd_vencidas(a):
    hoy = date.today()
    for cid, d, _ in clientes(todos=True):
        p = d / "content" / "tandas.json"
        tandas = _load(p, {})
        cambio = False
        for t, v in tandas.items():
            if v.get("estado") == "pendiente" and (hoy - date.fromisoformat(v["creada"])).days >= PLAZO:
                v.update(estado="aprobada", aprobada=hoy.isoformat(), nota=f"aprobada sola tras {PLAZO} días sin comentarios")
                cambio = True
                print(f"✓ {cid}: tanda {t} aprobada sola (sin comentarios en {PLAZO} días)")
        if cambio:
            _save(p, tandas)


def cmd_avisos(a):
    hoy = date.fromisoformat(a.hoy) if a.hoy else None
    filas = [estado_cliente(c, d, p, hoy) for c, d, p in clientes()]
    L = []
    for f in filas:
        if f["necesita_tanda"] and f["dias_quedan"] <= max(7, f["minimo"] - 7):
            L.append(f"- **{f['cliente']}**: contenido hasta {f['contenido_hasta'] or '—'} (quedan {f['dias_quedan']} días). "
                     f"La tarea de tandas no lo ha cubierto: revísala o escribe la tanda a mano.")
        for t in f["tandas_pendientes"]:
            L.append(f"- **{f['cliente']}**: la tanda {t} sigue pendiente de aprobación.")
    if L and a.out:
        Path(a.out).write_text("\n".join(["Contenido que necesita atención:", ""] + L) + "\n", encoding="utf-8")
    print("\n".join(L) or "Todo en orden.")


def main():
    ap = argparse.ArgumentParser(description="Tandas de contenido")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("estado"); s.add_argument("--json", action="store_true"); s.add_argument("--hoy", help="simular otra fecha (pruebas)")
    s.set_defaults(fn=cmd_estado)
    s = sub.add_parser("cerrar"); s.add_argument("--cliente", required=True); s.add_argument("--tanda"); s.set_defaults(fn=cmd_cerrar)
    s = sub.add_parser("aprobar"); s.add_argument("--cliente", required=True); s.add_argument("tanda", nargs="?"); s.set_defaults(fn=cmd_aprobar)
    s = sub.add_parser("vencidas"); s.set_defaults(fn=cmd_vencidas)
    s = sub.add_parser("avisos"); s.add_argument("--out"); s.add_argument("--hoy"); s.set_defaults(fn=cmd_avisos)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

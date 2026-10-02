"""Coloca en el calendario las publicaciones nuevas de content/posts.json siguiendo content/plan.json.

Uso:
  python planificar.py --cliente demo --check    valida posts.json y dice cuántos días de contenido quedan
  python planificar.py --cliente demo --dry-run  enseña qué se programaría, sin guardar nada
  python planificar.py --cliente demo            programa las publicaciones que aún no están en el calendario

Reglas (todas en content/plan.json):
- Carrusel en los días y a la hora del plan; cada carrusel lleva su historia «¿Sabías que…?» ese
  mismo día (id f-<id>).
- Los posts del pilar de pregunta (marca.json → pilar_pregunta) son historias y salen el día/hora de
  plan["pregunta"] (en planes antiguos, plan["tu_turno"]).
- Reels en los días del plan: cada reel desarrolla el SIGUIENTE carrusel programado (normalmente el del
  día siguiente), elegido de los pilares que mejor funcionan en vídeo (plan["reels"]["pilares"]).
- Un post con "fecha": "AAAA-MM-DD" (p. ej. una fiesta) sale ese día si es día de carrusel; los demás se
  colocan alrededor sin adelantarlo.
- Nunca toca lo que ya está en el calendario: solo añade detrás de la última fecha.
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import cliente as C

POSTS = C.POSTS
REELS = C.REELS
PLAN = C.PLAN
CAL = C.CAL
PUBLISHED = C.PUBLISHED

DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3,
        "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6}
PILLARS = set(C.pilares())
PREGUNTA = C.pilar_pregunta()
QUERY_DEF = C.MARCA.get("video_query_defecto", "small business owner working")
# límites para que el texto quepa en las diapositivas (render.py reduce letra hasta un mínimo)
LIMITS = {"title": 70, "h": 60, "body": 260, "fact": 170, "cta": 80, "cta_sub": 110}


def load(p, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def weekdays(names):
    return {DIAS[n.lower()] for n in names}


def validate(posts):
    errs, seen = [], set()
    for p in posts:
        pid = p.get("id", "?")
        if pid in seen:
            errs.append(f"{pid}: id repetido")
        seen.add(pid)
        if p.get("pillar") not in PILLARS:
            errs.append(f"{pid}: pilar desconocido {p.get('pillar')}")
        need = ["title", "caption"] + ([] if p.get("pillar") == PREGUNTA else ["slides", "fact", "cta"])
        for k in need:
            if not p.get(k):
                errs.append(f"{pid}: falta «{k}»")
        if p.get("pillar") != PREGUNTA:
            sl = p.get("slides") or []
            if len(sl) != 2 or not all(s.get("h") and s.get("body") for s in sl):
                errs.append(f"{pid}: «slides» debe tener 2 elementos con h y body")
            for s in sl:
                for k in ("h", "body"):
                    if len(s.get(k, "")) > LIMITS[k]:
                        errs.append(f"{pid}: slide.{k} demasiado largo ({len(s[k])} > {LIMITS[k]})")
        for k in ("title", "fact", "cta", "cta_sub"):
            if len(p.get(k) or "") > LIMITS[k]:
                errs.append(f"{pid}: {k} demasiado largo ({len(p[k])} > {LIMITS[k]})")
        if len(p.get("caption", "")) > 2200:
            errs.append(f"{pid}: caption de más de 2200 caracteres (límite de Instagram)")
    return errs


def last_day(cal):
    if not cal["posts"]:
        return date.today()
    return max(datetime.fromisoformat(e["publish_at"]).date() for e in cal["posts"])


def plan_new(posts, cal, reels, plan, start=None):
    scheduled = {e["id"] for e in cal["posts"]}
    caro = [p for p in posts if p["pillar"] != PREGUNTA and p["id"] not in scheduled]
    turno = [p for p in posts if p["pillar"] == PREGUNTA and p["id"] not in scheduled]
    c_days = weekdays(plan["carrusel"]["dias"])
    r_days = weekdays(plan["reels"]["dias"]) if plan["reels"].get("activo", True) else set()
    preg = plan.get("pregunta") or plan.get("tu_turno") or {"activo": False}
    t_days = weekdays([preg["dia"]]) if preg.get("activo", True) and preg.get("dia") else set()
    reel_pillars = set(plan["reels"].get("pilares", []))
    used_queries = {r["query"] for r in reels["reels"]}

    d = start or max(last_day(cal), date.today()) + timedelta(days=1)
    new_cal, new_reels = [], []
    guard = 0
    reel_pendiente = None   # día de reel a la espera del siguiente carrusel que desarrollar
    while (caro or turno) and guard < 400:
        guard += 1
        if d.weekday() in r_days and reel_pendiente is None:
            reel_pendiente = d
        if d.weekday() in t_days and turno:
            p = turno.pop(0)
            new_cal.append({"id": p["id"], "type": "story", "publish_at": f"{d}T{preg['hora']}",
                            "files": [f"stories/{p['id']}.jpg"], "title": p["title"]})
        fijo = next((i for i, p in enumerate(caro) if p.get("fecha") == d.isoformat()), None)
        libres = [i for i, p in enumerate(caro) if not p.get("fecha") or p["fecha"] < d.isoformat()]
        if d.weekday() in c_days and caro and (fijo is not None or libres):
            reel_today = reel_pendiente is not None and reel_pendiente < d
            idx = fijo if fijo is not None else libres[0]
            if fijo is None and reel_today and reel_pillars:
                idx = next((i for i in libres if caro[i]["pillar"] in reel_pillars), idx)
            p = caro.pop(idx)
            if reel_today:
                q = p.get("video_query") or QUERY_DEF
                if q in used_queries:
                    q = f"{q} home"
                used_queries.add(q)
                rd = reel_pendiente
                reel_pendiente = None
                r = {"id": f"r-{p['id']}", "twin": p["id"], "query": q, "publish_at": f"{rd}T{plan['reels']['hora']}"}
                new_reels.append(r)
                new_cal.append({"id": r["id"], "type": "reel", "publish_at": r["publish_at"],
                                "files": [f"reels/{r['id']}.mp4"], "caption": p["caption"]})
            new_cal.append({"id": f"f-{p['id']}", "type": "story", "publish_at": f"{d}T{plan['dato']['hora']}",
                            "files": [f"stories/f-{p['id']}.jpg"], "title": f"{C.texto('dato')} · {p['title']}"})
            new_cal.append({"id": p["id"], "type": "carousel", "publish_at": f"{d}T{plan['carrusel']['hora']}",
                            "files": [f"carousels/{p['id']}/{i:02d}.jpg" for i in range(1, 6)],
                            "caption": p["caption"]})
        d += timedelta(days=1)
    new_cal.sort(key=lambda e: e["publish_at"])
    return new_cal, new_reels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    posts = load(POSTS)["posts"]
    cal = load(CAL, {"timezone": "Europe/Madrid", "posts": []})
    reels = load(REELS, {"reels": []})
    plan = load(PLAN)

    errs = validate(posts)
    if errs:
        print("✗ posts.json tiene errores:")
        for e in errs:
            print("  -", e)
        sys.exit(1)

    today = date.today()
    end = last_day(cal)
    print(f"Calendario hasta el {end} → quedan {(end - today).days} días de contenido programado.")
    if a.check:
        pending = [p["id"] for p in posts if p["id"] not in {e["id"] for e in cal["posts"]}]
        print(f"Posts escritos sin programar: {len(pending)}")
        return

    new_cal, new_reels = plan_new(posts, cal, reels, plan)
    if not new_cal:
        print("No hay posts nuevos que programar.")
        return
    kinds = {}
    for e in new_cal:
        kinds[e["type"]] = kinds.get(e["type"], 0) + 1
    print(f"Nuevas entradas: {kinds} · del {new_cal[0]['publish_at'][:10]} al {new_cal[-1]['publish_at'][:10]}")
    for e in new_cal[:12]:
        print(f"  {e['publish_at']}  {e['type']:8} {e['id']}")
    if len(new_cal) > 12:
        print(f"  … y {len(new_cal) - 12} más")
    if a.dry_run:
        return
    cal["posts"].extend(new_cal)
    cal["posts"].sort(key=lambda e: e["publish_at"])
    reels["reels"].extend(new_reels)
    save(CAL, cal)
    save(REELS, reels)
    print("✓ Calendario y reels actualizados.")


if __name__ == "__main__":
    main()

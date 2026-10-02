"""Tanda de EJEMPLO para clientes de ensayo: textos de relleno con los temas del cliente, para probar el flujo
completo (planificar → imágenes → cuaderno → revisión del cliente → publicación simulada) sin escribir contenido real.

Uso:  python motor/tanda_ejemplo.py --cliente <id> [--dias 35]
Solo funciona con clientes de ensayo (plan.json → "ensayo": true) que NO estén activos: nunca mete relleno en un
cliente real. El contenido de verdad lo escribe la tarea de Claude (tareas/tandas.md).
"""
from __future__ import annotations

import argparse
import json
import math

import cliente as C

DIAS_SEMANA = 7


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int)
    a = ap.parse_args()
    plan = C.plan()
    if plan.get("activo") or not plan.get("ensayo"):
        raise SystemExit("Solo para clientes de ensayo que no estén activos (plan.json → \"ensayo\": true, \"activo\": false).")
    dias = a.dias or (plan.get("tanda") or {}).get("dias_por_tanda", 35)
    semanas = math.ceil(dias / DIAS_SEMANA)
    n_car = semanas * len((plan.get("carrusel") or {}).get("dias", ["lunes", "miercoles", "viernes"]))
    preg = plan.get("pregunta") or plan.get("tu_turno") or {}
    n_preg = semanas if preg.get("activo", True) else 0

    pil = C.pilares()
    pq = C.pilar_pregunta()
    temas = [k for k in pil if k != pq] or ["P1"]
    try:
        muestras = json.loads((C.CONTENT / "muestras.json").read_text(encoding="utf-8"))["posts"]
    except (OSError, ValueError, KeyError):
        muestras = []
    base = next((m for m in muestras if m.get("slides")), None)
    posts_doc = json.loads(C.POSTS.read_text(encoding="utf-8")) if C.POSTS.exists() else {"posts": []}
    hechos = {p["id"] for p in posts_doc["posts"]}
    k = 1
    while any(i.startswith(f"ej{k}-") for i in hechos):
        k += 1
    pref = f"ej{k}"
    nuevos = []
    for i in range(1, n_car + 1):
        pid = temas[(i - 1) % len(temas)]
        tema = pil.get(pid, pid)
        slides = (base or {}).get("slides") or [{"h": "Primera idea", "body": "Aquí irá la primera idea del post."},
                                                 {"h": "Segunda idea", "body": "Aquí irá la segunda idea del post."}]
        nuevos.append({"id": f"{pref}-{i:02d}", "pillar": pid, "ejemplo": True,
                       "title": f"{tema} · ejemplo {i}",
                       "slides": slides,
                       "fact": (base or {}).get("fact") or "Aquí irá un dato curioso del negocio.",
                       "cta": "¿Qué te parece?",
                       "caption": f"[EJEMPLO] {tema}. Este texto lo escribirá la tarea de contenido con la voz del negocio.",
                       "video_query": C.MARCA.get("video_query_defecto", "small business owner working"),
                       "foto_query": C.MARCA.get("video_query_defecto", "small business")})
    for j in range(1, n_preg + 1):
        nuevos.append({"id": f"{pref}-q{j}", "pillar": pq or temas[0], "ejemplo": True,
                       "title": "¿Qué te gustaría que te contáramos por aquí?", "cta": C.texto("responde"),
                       "caption": "[EJEMPLO] Pregunta de la semana"})
    posts_doc["posts"].extend(nuevos)
    C.POSTS.write_text(json.dumps(posts_doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✓ Tanda de ejemplo {pref}: {n_car} carruseles y {n_preg} preguntas escritos (relleno, solo para ensayo).")


if __name__ == "__main__":
    main()

"""Métricas del Instagram del cliente: guarda las estadísticas de cada publicación y hace el informe semanal.

Uso:
  python metricas.py                       recoge/actualiza métricas (historias: hay que leerlas antes de 24 h)
  python metricas.py --informe x.md        además escribe el informe semanal en x.md
                                           y actualiza content/aprendizajes.md (lo lee la tarea de tandas)

Datos en content/metricas.json. Necesita el permiso instagram_business_manage_insights.
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cliente as C
import config
import instagram_api as ig

BASE = config.BASE_DIR
DATA = C.CONTENT / "metricas.json"
LEARN = C.CONTENT / "aprendizajes.md"
POSTS = C.POSTS
REELS = C.REELS
CAL = C.CAL

METRICS = {
    "carousel": ["reach", "views", "likes", "comments", "saved", "shares", "total_interactions"],
    "reel": ["reach", "views", "likes", "comments", "saved", "shares", "total_interactions", "ig_reels_avg_watch_time"],
    "story": ["reach", "views", "replies", "shares", "total_interactions", "navigation"],
}
PILLARS = C.pilares()
DAYS_TRACKED = {"story": 1, "carousel": 30, "reel": 30}   # cuánto tiempo se siguen actualizando


def _load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _insights(media_id: str, metrics: list[str]) -> dict:
    def ask(ms):
        data = ig._call("GET", f"{media_id}/insights", metric=",".join(ms))
        out = {}
        for d in data.get("data", []):
            v = d.get("total_value", {}).get("value") if "total_value" in d else (d.get("values") or [{}])[0].get("value")
            out[d["name"]] = v
        return out
    try:
        return ask(metrics)
    except RuntimeError:          # alguna métrica no aplica a este contenido: se piden de una en una
        out = {}
        for m in metrics:
            try:
                out.update(ask([m]))
            except RuntimeError:
                pass
        return out


def score(m: dict) -> float:
    """Interés real: guardados y compartidos pesan más que los me gusta."""
    return (m.get("saved") or 0) * 3 + (m.get("shares") or 0) * 3 + (m.get("comments") or 0) * 2 + (m.get("likes") or 0)


def collect():
    published = _load(C.PUBLISHED, {})
    cal = {e["id"]: e for e in _load(CAL, {"posts": []})["posts"]}
    data = _load(DATA, {})
    now = datetime.now(timezone.utc)
    n = 0
    for pid, info in published.items():
        kind = cal.get(pid, {}).get("type", "carousel")
        when = datetime.fromisoformat(info["published_at"])
        if now - when > timedelta(days=DAYS_TRACKED.get(kind, 30)) and pid in data:
            continue   # ya cerrado
        if now - when > timedelta(days=DAYS_TRACKED.get(kind, 30)) and kind == "story":
            continue   # historia caducada sin datos
        m = _insights(info["media_id"], METRICS.get(kind, METRICS["carousel"]))
        if m:
            data[pid] = {"type": kind, "published_at": info["published_at"], "permalink": info.get("permalink", ""),
                         "updated": now.isoformat(timespec="minutes"), **m}
            n += 1
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Métricas actualizadas: {n} publicaciones ({len(data)} en total).")
    return data


def _meta():
    posts = {p["id"]: p for p in _load(POSTS, {"posts": []})["posts"]}
    twin = {r["id"]: r["twin"] for r in _load(REELS, {"reels": []})["reels"]}

    def info(pid):
        base = twin.get(pid) or (pid[2:] if pid.startswith("f-") else pid)
        p = posts.get(base, {})
        return p.get("title", pid), p.get("pillar", "?")
    return info


def report(data: dict, out: Path):
    info = _meta()
    now = datetime.now(timezone.utc)
    week = {k: v for k, v in data.items() if now - datetime.fromisoformat(v["published_at"]) <= timedelta(days=7)}
    feed = {k: v for k, v in data.items() if v["type"] in ("carousel", "reel")}
    L = [f"# Informe semanal de Instagram · @{C.usuario()} · {datetime.now().strftime('%d/%m/%Y')}", ""]
    if not week:
        L.append("Esta semana no hay publicaciones con métricas todavía.")
    else:
        tot = defaultdict(int)
        for v in week.values():
            for k in ("reach", "likes", "comments", "saved", "shares"):
                tot[k] += v.get(k) or 0
        L += [f"**Últimos 7 días:** {len(week)} publicaciones · alcance sumado {tot['reach']:,} · "
              f"{tot['saved']} guardados · {tot['shares']} compartidos · {tot['comments']} comentarios · {tot['likes']} me gusta", ""]
        L += ["## Lo mejor de la semana (guardados y compartidos pesan más)", "",
              "| | Publicación | Tipo | Alcance | Guard. | Comp. | Coment. |", "|---|---|---|---|---|---|---|"]
        for i, (k, v) in enumerate(sorted(((k, v) for k, v in week.items() if v["type"] != "story"),
                                          key=lambda kv: score(kv[1]), reverse=True)[:5], 1):
            t, _ = info(k)
            L.append(f"| {i} | [{t[:55]}]({v.get('permalink', '')}) | {v['type']} | {v.get('reach', 0)} | "
                     f"{v.get('saved', 0)} | {v.get('shares', 0)} | {v.get('comments', 0)} |")
        L.append("")
    # acumulado por pilar y por formato (todo el histórico del feed)
    by_p, by_t = defaultdict(list), defaultdict(list)
    for k, v in feed.items():
        by_p[info(k)[1]].append(v)
        by_t[v["type"]].append(v)
    if feed:
        def avg(vs, key):
            return sum((v.get(key) or 0) for v in vs) / max(1, len(vs))
        L += ["## Qué funciona (histórico)", "", "| Pilar | Nº | Alcance medio | Interés medio* |", "|---|---|---|---|"]
        ranking = sorted(by_p.items(), key=lambda kv: sum(score(v) for v in kv[1]) / len(kv[1]), reverse=True)
        for p, vs in ranking:
            L.append(f"| {PILLARS.get(p, p)} | {len(vs)} | {avg(vs, 'reach'):.0f} | {sum(score(v) for v in vs) / len(vs):.1f} |")
        L += ["", "| Formato | Nº | Alcance medio | Interés medio* |", "|---|---|---|---|"]
        for t, vs in by_t.items():
            L.append(f"| {t} | {len(vs)} | {avg(vs, 'reach'):.0f} | {sum(score(v) for v in vs) / len(vs):.1f} |")
        L += ["", "*Interés = guardados×3 + compartidos×3 + comentarios×2 + me gusta."]
        # aprendizajes para la tarea de tandas
        solid = [(p, vs) for p, vs in ranking if len(vs) >= 3]   # con menos de 3 publicaciones no se concluye nada
        top = [PILLARS.get(p, p) for p, _ in solid[:3]]
        low = [PILLARS.get(p, p) for p, _ in solid[-2:]] if len(solid) > 4 else []
        best = sorted(feed.items(), key=lambda kv: score(kv[1]), reverse=True)[:8]
        learn = [f"# Aprendizajes de métricas (actualizado {datetime.now().strftime('%d/%m/%Y')})", "",
                 "Lo genera metricas.py cada semana. La tarea de tandas lo usa para decidir temas y reparto.", "",
                 f"- Pilares que mejor funcionan: {', '.join(top)}." if top else
                 "- Aún hay pocos datos por pilar (menos de 3 publicaciones cada uno): no cambies el reparto todavía.",
                 f"- Pilares más flojos (reducir o cambiar enfoque): {', '.join(low)}." if low else "",
                 "- Publicaciones con más interés (haz más con este enfoque):"]
        learn += [f"  - {info(k)[0]} ({v['type']}, {v.get('saved', 0)} guardados, {v.get('shares', 0)} compartidos)"
                  for k, v in best]
        LEARN.write_text("\n".join(x for x in learn if x != "") + "\n", encoding="utf-8")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--informe")
    a = ap.parse_args()
    data = collect()
    if a.informe:
        report(data, Path(a.informe))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        if "permission" in str(e).lower() or "(#10)" in str(e):
            print("✗ El token no tiene permiso para leer estadísticas (instagram_business_manage_insights).")
        print(f"Error: {e}")
        sys.exit(1)

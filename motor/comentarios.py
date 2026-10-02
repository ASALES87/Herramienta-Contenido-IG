"""Resumen de comentarios nuevos en el Instagram del cliente (para contestar pronto, que mejora el alcance).

Uso:
  python comentarios.py --cliente demo              imprime los comentarios nuevos desde la última revisión
  python comentarios.py --out x.md   además los escribe en x.md (lo usa GitHub para abrir un aviso)

Guarda en content/comentarios_vistos.json la hora del último comentario visto, para no repetir.
Necesita que el token tenga el permiso instagram_business_manage_comments.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cliente as C
import config
import instagram_api as ig

STATE = config.BASE_DIR / "content" / "comentarios_vistos.json"
OWN = C.usuario()


def _ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")


def _all(path: str, **params) -> list[dict]:
    out, data = [], ig._call("GET", path, **params)
    out += data.get("data", [])
    # una página suele bastar; seguimos como mucho 3 páginas
    for _ in range(2):
        nxt = (data.get("paging") or {}).get("cursors", {}).get("after")
        if not nxt or not (data.get("paging") or {}).get("next"):
            break
        data = ig._call("GET", path, after=nxt, **params)
        out += data.get("data", [])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--dias", type=int, default=30, help="revisar publicaciones de los últimos N días")
    a = ap.parse_args()

    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    since = _ts(state["ultimo"]) if state.get("ultimo") else datetime.now(timezone.utc) - timedelta(days=1)
    limit_media = datetime.now(timezone.utc) - timedelta(days=a.dias)

    media = _all(f"{config.IG_USER_ID}/media", fields="id,caption,permalink,timestamp,comments_count", limit=50)
    nuevos, newest = [], since
    for m in media:
        if _ts(m["timestamp"]) < limit_media or not m.get("comments_count"):
            continue
        for c in _all(f"{m['id']}/comments", fields="id,text,username,timestamp,replies{username}", limit=50):
            t = _ts(c["timestamp"])
            if t <= since or c.get("username") == OWN:
                continue
            answered = any(r.get("username") == OWN for r in (c.get("replies") or {}).get("data", []))
            nuevos.append((t, m, c, answered))
            newest = max(newest, t)

    if not nuevos:
        print("Sin comentarios nuevos.")
    else:
        nuevos.sort(key=lambda x: x[0])
        lines = [f"**{len(nuevos)} comentario(s) nuevo(s)** en @{OWN}. Contestar en la primera hora ayuda al alcance.", ""]
        for t, m, c, answered in nuevos:
            title = (m.get("caption") or "").splitlines()[0][:70] if m.get("caption") else m["id"]
            hora = t.astimezone().strftime("%d/%m %H:%M")
            lines.append(f"- **@{c.get('username', '?')}** · {hora} · [{title}]({m['permalink']})"
                         + (" · ✅ ya respondido" if answered else ""))
            lines.append(f"  > {c.get('text', '').strip()}")
        text = "\n".join(lines)
        print(text)
        if a.out:
            Path(a.out).write_text(text + "\n", encoding="utf-8")

    STATE.write_text(json.dumps({"ultimo": newest.strftime("%Y-%m-%dT%H:%M:%S%z")}, indent=1) + "\n",
                     encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        msg = str(e)
        if "permission" in msg.lower() or "(#10)" in msg or "(#200)" in msg:
            print("✗ El token no tiene permiso para leer comentarios (instagram_business_manage_comments).")
        print(f"Error: {msg}")
        sys.exit(1)

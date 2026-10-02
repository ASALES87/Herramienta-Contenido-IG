"""Calendario de publicaciones en JSON + registro de lo ya publicado (para no duplicar).

Las horas de content_calendar.json están en hora de Madrid (campo "timezone"),
así funciona igual en tu PC que en GitHub Actions (que va en UTC).
"""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import config


def _load(path: Path = config.CALENDAR_PATH) -> dict:
    if not path.exists():
        return {"timezone": "Europe/Madrid", "posts": []}
    return json.loads(path.read_text(encoding="utf-8"))


def tz() -> ZoneInfo:
    return ZoneInfo(_load().get("timezone", "Europe/Madrid"))


def load_calendar() -> list[dict]:
    return _load()["posts"]


def load_published() -> dict:
    if config.PUBLISHED_LOG.exists():
        return json.loads(config.PUBLISHED_LOG.read_text(encoding="utf-8"))
    return {}


def mark_published(post_id: str, media_id: str, permalink: str = "") -> None:
    log = load_published()
    log[post_id] = {"media_id": media_id, "permalink": permalink,
                    "published_at": datetime.now(tz()).isoformat(timespec="seconds")}
    config.PUBLISHED_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


def _when(p: dict) -> datetime:
    return datetime.fromisoformat(p["publish_at"]).replace(tzinfo=tz())


def bloqueados() -> set:
    """Publicaciones de tandas pendientes de aprobación (content/tandas.json): no se publican todavía."""
    try:
        t = json.loads((config.BASE_DIR / "content" / "tandas.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {pid for v in t.values() if v.get("estado") == "pendiente" for pid in v.get("posts", [])}


def due_posts(now: datetime | None = None) -> list[dict]:
    """Publicaciones con hora <= ahora que aún no se han publicado (la más antigua primero).
    Las de tandas pendientes de aprobación se saltan hasta que se aprueben."""
    now = now or datetime.now(tz())
    done = load_published()
    stop = bloqueados()
    out = [p for p in load_calendar() if p["id"] not in done and p["id"] not in stop and not p.get("skip") and _when(p) <= now]
    return sorted(out, key=_when)


def upcoming(n: int = 10) -> list[dict]:
    now = datetime.now(tz())
    done = load_published()
    fut = [p for p in load_calendar() if p["id"] not in done and not p.get("skip") and _when(p) > now]
    return sorted(fut, key=_when)[:n]


def resolve_media(post: dict) -> list[Path]:
    """Rutas de los archivos, relativas a la carpeta media/ salvo que sean absolutas."""
    files = []
    for f in post["files"]:
        p = Path(f)
        files.append(p if p.is_absolute() else config.MEDIA_DIR / p)
    missing = [str(p) for p in files if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Faltan archivos para '{post['id']}': {missing}  (¿has ejecutado render.py?)")
    return files

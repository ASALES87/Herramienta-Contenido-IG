"""Calendario de publicaciones en JSON + registro de lo ya publicado (para no duplicar).

Las horas de content_calendar.json están en hora de Madrid (campo "timezone"),
así funciona igual en tu PC que en GitHub Actions (que va en UTC).

Retrasos (lección de Kodomo, oct-2026): si una publicación llega más de plan.json → "retraso_max_horas" (3 h por
defecto; 0 = sin límite) tarde, no se publica fuera de hora: se pasa al siguiente hueco libre (una de las horas del
plan del cliente sin otra publicación) y se avisa. El cambio se guarda en content/reprogramados.json
({id: nueva fecha}) para que no lo pise planificar.py al añadir tandas.
"""
import json
import os
from datetime import datetime, timedelta
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


REPROGRAMADOS = config.BASE_DIR / "content" / "reprogramados.json"
RETRASO_DEF_H = 3


def load_reprogramados() -> dict:
    try:
        return json.loads(REPROGRAMADOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _hora_efectiva(p: dict, rep: dict | None = None) -> str:
    rep = load_reprogramados() if rep is None else rep
    return (rep.get(p["id"]) or {}).get("publish_at") or p["publish_at"]


def _when(p: dict, rep: dict | None = None) -> datetime:
    return datetime.fromisoformat(_hora_efectiva(p, rep)).replace(tzinfo=tz())


def _plan() -> dict:
    try:
        return json.loads((config.BASE_DIR / "content" / "plan.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def retraso_max_horas() -> float:
    v = _plan().get("retraso_max_horas", RETRASO_DEF_H)
    return float(v or 0)


def horas_plan() -> list[str]:
    plan = _plan()
    hs = {(plan.get(k) or {}).get("hora") for k in ("carrusel", "dato", "pregunta", "tu_turno", "reels")}
    return sorted(h for h in hs if h) or ["08:00", "13:30"]


def _siguiente_hueco(desde: datetime, ocupadas: set) -> datetime:
    """Primera hora del plan posterior a «desde» en la que el cliente no tiene ya otra publicación."""
    dia = desde.date()
    for _ in range(120):
        for h in horas_plan():
            hh, mm = map(int, h.split(":"))
            t = datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=tz())
            if t > desde and t.strftime("%Y-%m-%dT%H:%M") not in ocupadas:
                return t
        dia += timedelta(days=1)
    raise RuntimeError("No hay huecos libres en los próximos 120 días")


def reprogramar_atrasados(now: datetime | None = None, persist: bool = True) -> list[dict]:
    """Pasa al siguiente hueco libre lo que llega más de retraso_max_horas tarde. Devuelve los cambios
    [{id, type, antes, ahora, retraso_h}]. Con persist=False solo informa (modo simular)."""
    limite = retraso_max_horas()
    if not limite:
        return []
    now = now or datetime.now(tz())
    rep = load_reprogramados()
    done = load_published()
    stop = bloqueados()
    cal = load_calendar()
    pend = [p for p in cal if p["id"] not in done and p["id"] not in stop and not p.get("skip")]
    tarde = sorted((p for p in pend if _when(p, rep) < now - timedelta(hours=limite)), key=lambda p: _when(p, rep))
    if not tarde:
        return []
    ocupadas = {_hora_efectiva(p, rep)[:16] for p in cal if p["id"] not in done}
    cambios = []
    for p in tarde:
        antes = _when(p, rep)
        nueva = _siguiente_hueco(now, ocupadas)
        ocupadas.add(nueva.strftime("%Y-%m-%dT%H:%M"))
        cambios.append({"id": p["id"], "type": p["type"], "antes": antes.strftime("%Y-%m-%dT%H:%M"),
                        "ahora": nueva.strftime("%Y-%m-%dT%H:%M"),
                        "retraso_h": round((now - antes).total_seconds() / 3600, 1)})
        rep[p["id"]] = {"publish_at": nueva.strftime("%Y-%m-%dT%H:%M"), "original": p["publish_at"],
                        "motivo": f"llegó {cambios[-1]['retraso_h']} h tarde (máx. {limite:g} h)",
                        "cuando": now.isoformat(timespec="seconds")}
    if persist:
        REPROGRAMADOS.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        avisos = os.getenv("AVISOS_FILE")
        if avisos:   # GitHub Actions: se convierte en un aviso (issue) al final de la ejecución
            with open(avisos, "a", encoding="utf-8") as f:
                for c in cambios:
                    f.write(f"- **{config.C.ID}** · `{c['id']}` ({c['type']}) debía salir el {c['antes'].replace('T', ' ')} "
                            f"y llegó {c['retraso_h']} h tarde → pasa al **{c['ahora'].replace('T', ' ')}**\n")
    return cambios


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
    rep = load_reprogramados()
    out = [p for p in load_calendar() if p["id"] not in done and p["id"] not in stop and not p.get("skip") and _when(p, rep) <= now]
    return [dict(p, publish_at=_hora_efectiva(p, rep)) for p in sorted(out, key=lambda p: _when(p, rep))]


def upcoming(n: int = 10) -> list[dict]:
    now = datetime.now(tz())
    done = load_published()
    rep = load_reprogramados()
    fut = [p for p in load_calendar() if p["id"] not in done and not p.get("skip") and _when(p, rep) > now]
    return [dict(p, publish_at=_hora_efectiva(p, rep)) for p in sorted(fut, key=lambda p: _when(p, rep))[:n]]


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

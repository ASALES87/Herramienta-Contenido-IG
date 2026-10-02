"""Cliente activo: carpeta, marca, rutas y credenciales.

Todos los scripts del motor trabajan sobre UN cliente, que se elige así (por orden):
  1. argumento  --cliente <id>   (en cualquier posición; se retira antes de leer el resto)
  2. variable de entorno CLIENTE
  3. si solo hay un cliente en clientes/ (sin contar _plantilla), ese.

Estructura de cada cliente (clientes/<id>/):
  marca.json        colores, fuentes, logo, @, pilares, destacadas, textos fijos
  content/          plan.json, posts.json, reels.json, content_calendar.json, published.json,
                    GUIA_TANDAS.md, metricas.json, aprendizajes.md, comentarios_vistos.json…
  assets/           logo.png, fonts/, music/
  media/            lo que se genera (no se sube a git)
  .env              credenciales locales (no se sube a git)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOTOR = ROOT / "motor"
CLIENTES = ROOT / "clientes"


def _id_desde_argv() -> str | None:
    for i, a in enumerate(sys.argv):
        if a == "--cliente" and i + 1 < len(sys.argv):
            v = sys.argv[i + 1]
            del sys.argv[i:i + 2]
            return v
        if a.startswith("--cliente="):
            del sys.argv[i]
            return a.split("=", 1)[1]
    return None


def _elegir() -> str:
    cid = _id_desde_argv() or os.getenv("CLIENTE")
    if cid:
        return cid
    todos = [p.name for p in CLIENTES.iterdir() if p.is_dir() and not p.name.startswith("_")] if CLIENTES.exists() else []
    if len(todos) == 1:
        return todos[0]
    raise SystemExit(f"Indica el cliente con --cliente <id> o CLIENTE=<id>. Disponibles: {', '.join(sorted(todos)) or 'ninguno'}")


ID = _elegir()
DIR = CLIENTES / ID
if not (DIR / "marca.json").exists():
    raise SystemExit(f"No existe {DIR / 'marca.json'}")

CONTENT = DIR / "content"
ASSETS = DIR / "assets"
MEDIA = DIR / "media"
POSTS = CONTENT / "posts.json"
REELS = CONTENT / "reels.json"
PLAN = CONTENT / "plan.json"
CAL = CONTENT / "content_calendar.json"
PUBLISHED = CONTENT / "published.json"

MARCA: dict = json.loads((DIR / "marca.json").read_text(encoding="utf-8"))


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8")) if PLAN.exists() else {}


def activo() -> bool:
    return bool(plan().get("activo", False))


# ---------- textos fijos (cada cliente puede cambiarlos en marca.json → "textos") ----------
TEXTOS_DEF = {
    "desliza": "Desliza",
    "cta_sub": "Guárdalo para tenerlo a mano y compártelo con quien lo necesite.",
    "dato": "¿Sabías que…?",
    "hoy_en_perfil": "HOY A LAS {hora} EN EL PERFIL",
    "responde": "Respóndenos por mensaje",
    "comenta": "Cuéntanoslo en comentarios",
    "pregunta": "Tu turno",
    "reel": "Reel",
}


def texto(clave: str, **kw) -> str:
    t = (MARCA.get("textos") or {}).get(clave, TEXTOS_DEF.get(clave, clave))
    return t.format(**kw) if kw else t


def pilares() -> dict:
    return MARCA.get("pilares", {})


def pilar_pregunta() -> str | None:
    """Pilar cuyos posts son una pregunta a la comunidad (se publican como historia, sin diapositivas)."""
    return MARCA.get("pilar_pregunta")


def usuario() -> str:
    return (MARCA.get("instagram") or "").lstrip("@")


def asset(rel: str | None) -> Path | None:
    """Ruta de un recurso del cliente (relativa a su carpeta) si existe."""
    if not rel:
        return None
    p = (DIR / rel) if not Path(rel).is_absolute() else Path(rel)
    return p if p.exists() else None


# ---------- credenciales ----------
def _cargar_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for f in (DIR / ".env", ROOT / ".env"):
        if f.exists():
            load_dotenv(f, override=False)


_cargar_env()
SUFIJO = ID.upper().replace("-", "_")


def secreto(nombre: str, defecto: str = "") -> str:
    """Primero el secreto propio del cliente (IG_ACCESS_TOKEN_DEMO), luego el común (IG_ACCESS_TOKEN)."""
    return os.getenv(f"{nombre}_{SUFIJO}") or os.getenv(nombre) or defecto


def guardar_secreto(nombre: str, valor: str) -> None:
    """Actualiza una credencial en el .env del cliente (si existe) y en memoria."""
    env = DIR / ".env"
    if env.exists():
        try:
            from dotenv import set_key
            set_key(str(env), nombre, valor, quote_mode="never")
        except ImportError:
            pass
    os.environ[f"{nombre}_{SUFIJO}"] = valor

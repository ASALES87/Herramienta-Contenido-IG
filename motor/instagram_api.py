"""Publicación en Instagram con la API de Instagram (inicio de sesión de Instagram).

Flujo: crear contenedor -> esperar a que esté FINISHED -> publicar.
Las imágenes/vídeos deben estar en una URL pública (ver media_host.py).
Límite de Meta: 100 publicaciones por API cada 24 h (un carrusel cuenta como 1).

Lección de Kodomo (oct-2026): media_publish a veces responde «media not ready» (código 9007, subcódigo 2207027)
aunque el contenedor diga FINISHED. Se reintenta hasta 8 veces con espera creciente (10 s, 20 s, 30 s…) y, antes de
cada reintento, se mira el status_code del contenedor: si ya es PUBLISHED, no se reintenta (evita duplicados).
Cualquier otro error se lanza tal cual.
"""
import time
from datetime import date, timedelta

import requests

import config


def _url(path: str) -> str:
    return f"{config.IG_GRAPH_BASE}/{path.lstrip('/')}"


class IGError(RuntimeError):
    """Error de la API de Instagram con su código y subcódigo (para decidir si se reintenta)."""

    def __init__(self, status: int, error):
        self.status = status
        self.error = error if isinstance(error, dict) else {"message": str(error)}
        self.code = self.error.get("code")
        self.subcode = self.error.get("error_subcode")
        super().__init__(f"Instagram API ({status}): {error}")


NO_LISTO = (9007, 2207027)   # «media not ready»
REINTENTOS_PUBLICAR = 8
ESPERA_BASE_S = 10
_sleep = time.sleep          # se sustituye en las pruebas


def _call(method: str, path: str, **params) -> dict:
    if not config.IG_ACCESS_TOKEN:
        raise RuntimeError("Falta IG_ACCESS_TOKEN en el .env")
    params["access_token"] = config.IG_ACCESS_TOKEN
    r = requests.request(method, _url(path), params=params if method == "GET" else None,
                         data=params if method != "GET" else None, timeout=60)
    data = r.json()
    if r.status_code >= 400 or "error" in data:
        raise IGError(r.status_code, data.get("error", data))
    return data


# ---------- comprobaciones y token ----------

def whoami() -> dict:
    return _call("GET", "me", fields="user_id,username,account_type,media_count")


def refresh_token() -> dict:
    """Renueva el token de larga duración (otros 60 días) y lo guarda en el .env.
    Solo funciona si el token actual tiene más de 24 h y no ha caducado.
    Devuelve {'expires': fecha, 'token': nuevo_token}."""
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": config.IG_ACCESS_TOKEN},
                     timeout=60)
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"No se pudo renovar el token: {data}")
    expires = date.today() + timedelta(seconds=int(data.get("expires_in", 0)))
    config.save_env("IG_ACCESS_TOKEN", data["access_token"])
    config.save_env("IG_TOKEN_EXPIRES", expires.isoformat())
    config.IG_ACCESS_TOKEN = data["access_token"]
    return {"expires": expires.isoformat(), "token": data["access_token"]}


# ---------- contenedores ----------

def _wait_ready(container_id: str, timeout_s: int = 600) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = _call("GET", container_id, fields="status_code,status").get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            info = _call("GET", container_id, fields="status")
            raise RuntimeError(f"Contenedor {container_id} en estado {status}: {info}")
        time.sleep(5)
    raise TimeoutError(f"El contenedor {container_id} no terminó de procesarse")


def _no_listo(e: Exception) -> bool:
    return isinstance(e, IGError) and e.code == NO_LISTO[0] and e.subcode == NO_LISTO[1]


def _estado(container_id: str) -> str:
    return (_call("GET", container_id, fields="status_code") or {}).get("status_code", "")


def _buscar_publicada(caption: str) -> str | None:
    """Si el contenedor ya está PUBLISHED, busca el id de la publicación entre las últimas de la cuenta."""
    try:
        recientes = _call("GET", f"{config.IG_USER_ID}/media", fields="id,caption,timestamp", limit=5).get("data", [])
    except Exception:
        return None
    for m in recientes:
        if (m.get("caption") or "") == (caption or ""):
            return m["id"]
    return None


def _publish(container_id: str, caption: str = "") -> str:
    _wait_ready(container_id)
    intento = 0
    while True:
        try:
            res = _call("POST", f"{config.IG_USER_ID}/media_publish", creation_id=container_id)
            return res["id"]
        except IGError as e:
            if not _no_listo(e) or intento >= REINTENTOS_PUBLICAR:
                raise
            intento += 1
            espera = ESPERA_BASE_S * intento
            print(f"  … Instagram dice «media not ready»; reintento {intento}/{REINTENTOS_PUBLICAR} en {espera} s")
            _sleep(espera)
            estado = _estado(container_id)
            if estado == "PUBLISHED":   # ya salió: no reintentar (sería un duplicado)
                mid = _buscar_publicada(caption) or f"container:{container_id}"
                print(f"  ✓ El contenedor ya estaba publicado ({mid}); no se reintenta")
                return mid
            if estado in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Contenedor {container_id} en estado {estado} tras «media not ready»") from e


def publish_photo(image_url: str, caption: str = "") -> str:
    c = _call("POST", f"{config.IG_USER_ID}/media", image_url=image_url, caption=caption)
    return _publish(c["id"], caption)


def publish_story(media_url: str) -> str:
    """Historia de imagen (JPEG 1080x1920). La API no permite stickers ni añadirla a destacadas."""
    c = _call("POST", f"{config.IG_USER_ID}/media", media_type="STORIES", image_url=media_url)
    return _publish(c["id"])


def publish_reel(video_url: str, caption: str = "", share_to_feed: bool = True, cover_url: str | None = None) -> str:
    params = dict(media_type="REELS", video_url=video_url, caption=caption,
                  share_to_feed=str(share_to_feed).lower())
    if cover_url:
        params["cover_url"] = cover_url
    c = _call("POST", f"{config.IG_USER_ID}/media", **params)
    return _publish(c["id"], caption)


def publish_carousel(media_urls: list[str], caption: str = "") -> str:
    """media_urls: 2-10 URLs (imágenes .jpg/.png o vídeos .mp4)."""
    if not 2 <= len(media_urls) <= 10:
        raise ValueError("Un carrusel necesita entre 2 y 10 elementos")
    children = []
    for u in media_urls:
        if u.lower().split("?")[0].endswith((".mp4", ".mov")):
            c = _call("POST", f"{config.IG_USER_ID}/media", media_type="VIDEO", video_url=u, is_carousel_item="true")
        else:
            c = _call("POST", f"{config.IG_USER_ID}/media", image_url=u, is_carousel_item="true")
        _wait_ready(c["id"])
        children.append(c["id"])
    parent = _call("POST", f"{config.IG_USER_ID}/media", media_type="CAROUSEL",
                   children=",".join(children), caption=caption)
    return _publish(parent["id"], caption)


def permalink(media_id: str) -> str:
    if str(media_id).startswith("container:"):
        return ""
    return _call("GET", media_id, fields="permalink").get("permalink", "")

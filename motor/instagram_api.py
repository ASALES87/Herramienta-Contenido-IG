"""Publicación en Instagram con la API de Instagram (inicio de sesión de Instagram).

Flujo: crear contenedor -> esperar a que esté FINISHED -> publicar.
Las imágenes/vídeos deben estar en una URL pública (ver media_host.py).
Límite de Meta: 100 publicaciones por API cada 24 h (un carrusel cuenta como 1).
"""
import time
from datetime import date, timedelta

import requests

import config


def _url(path: str) -> str:
    return f"{config.IG_GRAPH_BASE}/{path.lstrip('/')}"


def _call(method: str, path: str, **params) -> dict:
    if not config.IG_ACCESS_TOKEN:
        raise RuntimeError("Falta IG_ACCESS_TOKEN en el .env")
    params["access_token"] = config.IG_ACCESS_TOKEN
    r = requests.request(method, _url(path), params=params if method == "GET" else None,
                         data=params if method != "GET" else None, timeout=60)
    data = r.json()
    if r.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Instagram API ({r.status_code}): {data.get('error', data)}")
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


def _publish(container_id: str) -> str:
    _wait_ready(container_id)
    res = _call("POST", f"{config.IG_USER_ID}/media_publish", creation_id=container_id)
    return res["id"]


def publish_photo(image_url: str, caption: str = "") -> str:
    c = _call("POST", f"{config.IG_USER_ID}/media", image_url=image_url, caption=caption)
    return _publish(c["id"])


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
    return _publish(c["id"])


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
    return _publish(parent["id"])


def permalink(media_id: str) -> str:
    return _call("GET", media_id, fields="permalink").get("permalink", "")

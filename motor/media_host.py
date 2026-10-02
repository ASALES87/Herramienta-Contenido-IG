"""Aloja una imagen o vídeo en una URL pública (Instagram la descarga desde ahí).

Proveedor según marca.json → "media_host" o el secreto MEDIA_HOST:
  r2        Cloudflare R2 (capa gratuita, sin coste de salida). Secretos R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
            R2_SECRET_ACCESS_KEY, R2_BUCKET y R2_PUBLIC_URL (dominio público del bucket).
  shopify   Shopify Files (para clientes con tienda Shopify). Ver shopify_media.py.
  simulado  no sube nada; devuelve una URL ficticia (pruebas sin cuentas).

Interfaz única:  upload_file(path, filename=None) -> url
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import mimetypes
import urllib.parse
from pathlib import Path

import requests

import cliente as C
import config


def upload_file(path: str | Path, filename: str | None = None) -> str:
    path = Path(path)
    name = filename or path.name
    proveedor = config.MEDIA_HOST
    if proveedor == "simulado":
        return f"https://simulado.invalid/{C.ID}/{name}"
    if proveedor == "shopify":
        import shopify_media
        return shopify_media.upload_file(path, filename=name)
    if proveedor == "r2":
        return _r2_put(path, f"{C.ID}/{name}")
    raise RuntimeError(f"Proveedor de medios desconocido: {proveedor}")


# ---------- Cloudflare R2 (API compatible con S3, firma AWS v4 sin dependencias) ----------

def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def _r2_put(path: Path, key: str) -> str:
    falta = [n for n in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_URL")
             if not getattr(config, n)]
    if falta:
        raise RuntimeError(f"Faltan credenciales de R2: {', '.join(falta)}")
    host = f"{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    body = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    now = dt.datetime.now(dt.timezone.utc)
    amz_date, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()
    uri = "/" + urllib.parse.quote(f"{config.R2_BUCKET}/{key}")
    headers = {"host": host, "content-type": mime, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    signed = ";".join(sorted(headers))
    canonical = "\n".join(["PUT", uri, "", "".join(f"{k}:{headers[k]}\n" for k in sorted(headers)), signed, payload_hash])
    scope = f"{day}/auto/s3/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k = _sign(_sign(_sign(_sign(("AWS4" + config.R2_SECRET_ACCESS_KEY).encode(), day), "auto"), "s3"), "aws4_request")
    signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    auth = f"AWS4-HMAC-SHA256 Credential={config.R2_ACCESS_KEY_ID}/{scope}, SignedHeaders={signed}, Signature={signature}"
    r = requests.put(f"https://{host}{uri}", data=body, timeout=300,
                     headers={**{k: v for k, v in headers.items() if k != "host"}, "Authorization": auth})
    if r.status_code >= 300:
        raise RuntimeError(f"R2 rechazó la subida ({r.status_code}): {r.text[:300]}")
    return f"{config.R2_PUBLIC_URL}/{urllib.parse.quote(key)}"

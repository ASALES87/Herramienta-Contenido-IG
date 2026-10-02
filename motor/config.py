"""Configuración del cliente activo (credenciales y rutas). Ver cliente.py."""
import cliente as C

BASE_DIR = C.DIR

# Instagram (secretos con sufijo del cliente: IG_ACCESS_TOKEN_DEMO, IG_USER_ID_DEMO…)
IG_APP_ID = C.secreto("IG_APP_ID")
IG_APP_SECRET = C.secreto("IG_APP_SECRET")
IG_USER_ID = C.secreto("IG_USER_ID") or "me"
IG_ACCESS_TOKEN = C.secreto("IG_ACCESS_TOKEN")
IG_TOKEN_EXPIRES = C.secreto("IG_TOKEN_EXPIRES")
IG_GRAPH_BASE = C.secreto("IG_GRAPH_BASE") or "https://graph.instagram.com/v25.0"

# Alojamiento de medios (ver media_host.py)
MEDIA_HOST = (C.MARCA.get("media_host") or C.secreto("MEDIA_HOST") or "r2").lower()
SHOPIFY_STORE = C.secreto("SHOPIFY_STORE")
SHOPIFY_ADMIN_API_TOKEN = C.secreto("SHOPIFY_ADMIN_API_TOKEN")
SHOPIFY_API_VERSION = C.secreto("SHOPIFY_API_VERSION") or "2026-07"
R2_ACCOUNT_ID = C.secreto("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = C.secreto("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = C.secreto("R2_SECRET_ACCESS_KEY")
R2_BUCKET = C.secreto("R2_BUCKET")
R2_PUBLIC_URL = C.secreto("R2_PUBLIC_URL").rstrip("/")   # p. ej. https://pub-xxxx.r2.dev o https://media.tudominio.com

# Calendario
CALENDAR_PATH = C.CAL
PUBLISHED_LOG = C.PUBLISHED
MEDIA_DIR = C.MEDIA


def save_env(key: str, value: str) -> None:
    C.guardar_secreto(key, value)
    globals()[key] = value

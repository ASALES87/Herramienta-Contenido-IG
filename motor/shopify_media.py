"""Sube una imagen o vídeo local a Shopify Files y devuelve su URL pública (CDN).

Instagram necesita descargar el contenido desde una URL pública; usamos el CDN
de Shopify (incluido en la tienda, sin coste extra).
Requiere una App personalizada de Shopify con los scopes write_files y read_files.
"""
import mimetypes
import time
from pathlib import Path

import requests

import config

STAGED_UPLOAD = """
mutation StagedUpload($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets { url resourceUrl parameters { name value } }
    userErrors { field message }
  }
}"""

FILE_CREATE = """
mutation FileCreate($files: [FileCreateInput!]!) {
  fileCreate(files: $files) {
    files { id fileStatus }
    userErrors { field message }
  }
}"""

FILE_STATUS = """
query FileStatus($id: ID!) {
  node(id: $id) {
    ... on MediaImage { fileStatus image { url } }
    ... on Video { fileStatus sources { url mimeType } }
    ... on GenericFile { fileStatus url }
  }
}"""


def _gql(query: str, variables: dict) -> dict:
    if not config.SHOPIFY_ADMIN_API_TOKEN:
        raise RuntimeError("Falta SHOPIFY_ADMIN_API_TOKEN en el .env")
    url = f"https://{config.SHOPIFY_STORE}/admin/api/{config.SHOPIFY_API_VERSION}/graphql.json"
    r = requests.post(
        url,
        json={"query": query, "variables": variables},
        headers={"X-Shopify-Access-Token": config.SHOPIFY_ADMIN_API_TOKEN},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(f"Shopify GraphQL: {data['errors']}")
    return data["data"]


def upload_file(path: str | Path, filename: str | None = None, timeout_s: int = 300) -> str:
    """Sube el archivo y devuelve la URL pública cuando Shopify lo ha procesado.
    filename: nombre con el que se guarda en Shopify (por defecto, el del archivo)."""
    path = Path(path)
    fname = filename or path.name
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    is_video = mime.startswith("video/")
    resource = "VIDEO" if is_video else "IMAGE"

    staged_input = {
        "filename": fname,
        "mimeType": mime,
        "resource": resource,
        "httpMethod": "POST",
    }
    if is_video:
        staged_input["fileSize"] = str(path.stat().st_size)

    res = _gql(STAGED_UPLOAD, {"input": [staged_input]})["stagedUploadsCreate"]
    if res["userErrors"]:
        raise RuntimeError(f"stagedUploadsCreate: {res['userErrors']}")
    target = res["stagedTargets"][0]

    form = {p["name"]: p["value"] for p in target["parameters"]}
    with path.open("rb") as fh:
        up = requests.post(target["url"], data=form, files={"file": (fname, fh, mime)}, timeout=600)
    if up.status_code >= 300:
        raise RuntimeError(f"Subida fallida ({up.status_code}): {up.text[:300]}")

    res = _gql(FILE_CREATE, {"files": [{"originalSource": target["resourceUrl"], "contentType": resource, "filename": fname}]})["fileCreate"]
    if res["userErrors"]:
        raise RuntimeError(f"fileCreate: {res['userErrors']}")
    file_id = res["files"][0]["id"]

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        node = _gql(FILE_STATUS, {"id": file_id})["node"] or {}
        status = node.get("fileStatus")
        if status == "READY":
            if "image" in node and node["image"]:
                return node["image"]["url"]
            if "sources" in node and node["sources"]:
                mp4 = [s for s in node["sources"] if s["mimeType"] == "video/mp4"]
                return (mp4 or node["sources"])[0]["url"]
            if node.get("url"):
                return node["url"]
        if status == "FAILED":
            raise RuntimeError(f"Shopify no pudo procesar {path.name}")
        time.sleep(5)
    raise TimeoutError(f"Shopify tardó demasiado en procesar {path.name}")

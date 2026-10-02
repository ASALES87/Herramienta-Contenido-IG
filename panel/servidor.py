"""Panel de la Herramienta Contenido IG: todo el flujo en una página, sobre el motor de verdad.

Uso:  python panel/servidor.py [--puerto 8765] [--sin-navegador]
      (en Windows, doble clic en «Abrir panel.cmd»)

Abre http://127.0.0.1:8765 con:
  /              panel interno: clientes, alta, muestras, fotos, tandas, revisión, publicación simulada
  /asistente     asistente de alta; al final, «Crear cliente en el panel» lo da de alta directamente
  /c/<id>        vista del cliente: sus próximas publicaciones, aprobar o pedir cambios por número

Solo escucha en este ordenador (127.0.0.1). No muestra ni guarda tokens ni contraseñas, no publica en Instagram
(la publicación aquí es siempre simulada) y no activa clientes: eso sigue siendo un paso manual del checklist.

Pensado para crecer: toda la lógica va por la API JSON (/api/...), así que mañana las mismas páginas pueden
servirse desde un servidor en la nube con acceso por cliente sin cambiar el motor.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
PANEL = Path(__file__).resolve().parent
CLIENTES = ROOT / "clientes"
MOTOR = ROOT / "motor"
sys.path.insert(0, str(MOTOR))
import tandas as T  # noqa: E402  (solo funciones; no elige cliente al importarse)

ID_OK = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")
LOCK = threading.Lock()   # una acción del motor cada vez (escriben en los mismos archivos)
TIPOS = {"carousel": "Carrusel", "reel": "Reel", "story": "Historia"}


# ---------------- utilidades ----------------
def load(p: Path, d):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return d


def save(p: Path, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def env_utf8():
    e = dict(os.environ)
    e["PYTHONIOENCODING"] = "utf-8"
    e["PYTHONUTF8"] = "1"
    return e


def correr(args: list, timeout=600) -> tuple[int, str]:
    """Ejecuta un script del repo y devuelve (código, salida)."""
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, capture_output=True, env=env_utf8(),
                           timeout=timeout)
        out = (r.stdout + r.stderr).decode("utf-8", errors="replace").strip()
        code = r.returncode
    except subprocess.TimeoutExpired:
        code, out = 1, f"Se ha pasado de {timeout} s y se ha cortado."
    return code, f"{out}\n({time.time() - t0:.1f} s)".strip()


def cliente_dir(cid: str) -> Path:
    if not ID_OK.match(cid or "") or not (CLIENTES / cid / "marca.json").exists():
        raise LookupError(f"No existe el cliente {cid}")
    return CLIENTES / cid


def media_url(cid, rel):
    return f"/media/{cid}/{rel}"


def es_referencia(d: Path) -> bool:
    return bool(load(d / "marca.json", {}).get("solo_referencia"))


# ---------------- lectura del estado ----------------
def resumen(cid: str) -> dict:
    d = cliente_dir(cid)
    marca = load(d / "marca.json", {})
    plan = load(d / "content" / "plan.json", {})
    est = T.estado_cliente(cid, d, plan)
    tok = load(d / "content" / "token.json", {})
    perfil = d / "media" / "perfil.jpg"
    muestra = d / "media" / "muestras" / "mosaico.jpg"
    return {
        "id": cid, "nombre": marca.get("nombre", cid), "instagram": marca.get("instagram", ""),
        "sector": marca.get("sector", ""), "colores": marca.get("colores", {}),
        "estado": "activo" if plan.get("activo") else ("ensayo" if plan.get("ensayo") else "en alta"),
        "contenido_hasta": est["contenido_hasta"], "dias_quedan": est["dias_quedan"], "minimo": est["minimo"],
        "necesita_tanda": est["necesita_tanda"], "tandas_pendientes": est["tandas_pendientes"],
        "posts_sin_programar": est["posts_sin_programar"], "cambios_por_hacer": est["cambios_por_hacer"],
        "token_caduca": tok.get("caduca"),
        "imagen": media_url(cid, "perfil.jpg") if perfil.exists() else (
            media_url(cid, "muestras/mosaico.jpg") if muestra.exists() else None),
    }


def lista_clientes() -> list:
    out = []
    for d in sorted(CLIENTES.iterdir()):
        if d.is_dir() and not d.name.startswith("_") and (d / "marca.json").exists() and not es_referencia(d):
            try:
                out.append(resumen(d.name))
            except Exception as e:   # un cliente roto no tumba el panel
                out.append({"id": d.name, "nombre": d.name, "error": str(e)})
    return out


def items_tanda(d: Path, v: dict) -> list:
    """Publicaciones de una tanda en el mismo orden y numeración que el cuaderno PDF (revision.py)."""
    cal = load(d / "content" / "content_calendar.json", {"posts": []})["posts"]
    desde, hasta = date.fromisoformat(v["desde"]), date.fromisoformat(v["hasta"])
    return sorted((e for e in cal if desde <= datetime.fromisoformat(e["publish_at"]).date() <= hasta
                   and not e.get("skip") and not e["id"].startswith("f-")), key=lambda e: e["publish_at"])


def ficha_item(cid, d, e, posts, reels, publicados, bloqueados, num=None):
    media = d / "media"
    files = []
    for f in e.get("files", []):
        if f.endswith(".mp4"):
            cov = f"reels/{e['id']}_cover.jpg"
            if (media / f).exists():
                files.append({"tipo": "video", "url": media_url(cid, f),
                              "poster": media_url(cid, cov) if (media / cov).exists() else None})
            elif (media / cov).exists():
                files.append({"tipo": "imagen", "url": media_url(cid, cov), "nota": "portada (el vídeo se monta al publicar)"})
        elif (media / f).exists():
            files.append({"tipo": "imagen", "url": media_url(cid, f)})
    p = posts.get(e["id"]) or posts.get((reels.get(e["id"]) or {}).get("twin"), {})
    dt = datetime.fromisoformat(e["publish_at"])
    if e["id"] in publicados:
        estado = "publicada"
    elif e["id"] in bloqueados:
        estado = "en revisión"
    elif dt < datetime.now():
        estado = "atrasada"
    else:
        estado = "programada"
    guion = None
    if e["type"] == "reel" and p.get("slides"):
        guion = [p.get("title", ""), *(f"{s['h']}. {s['body']}" for s in p["slides"][:2]), p.get("fact", ""), p.get("cta", "")]
    return {"n": num, "id": e["id"], "tipo": e["type"], "tipo_txt": TIPOS.get(e["type"], e["type"]),
            "fecha": e["publish_at"], "estado": estado, "titulo": p.get("title") or e.get("title", ""),
            "pilar": p.get("pillar"), "caption": e.get("caption") or p.get("caption", ""), "archivos": files,
            "guion": guion, "ejemplo": bool(p.get("ejemplo")),
            "permalink": (publicados.get(e["id"]) or {}).get("permalink") if isinstance(publicados.get(e["id"]), dict) else None}


def detalle(cid: str) -> dict:
    d = cliente_dir(cid)
    r = resumen(cid)
    marca = load(d / "marca.json", {})
    plan = load(d / "content" / "plan.json", {})
    posts = {p["id"]: p for p in load(d / "content" / "posts.json", {"posts": []})["posts"]}
    reels = {x["id"]: x for x in load(d / "content" / "reels.json", {"reels": []})["reels"]}
    cal = load(d / "content" / "content_calendar.json", {"posts": []})["posts"]
    publicados = load(d / "content" / "published.json", {})
    tandas = load(d / "content" / "tandas.json", {})
    bloqueados = {i for v in tandas.values() if v.get("estado") == "pendiente" for i in v.get("posts", [])}
    hoy = datetime.now().replace(hour=0, minute=0)
    proximas = [ficha_item(cid, d, e, posts, reels, publicados, bloqueados)
                for e in sorted(cal, key=lambda e: e["publish_at"])
                if datetime.fromisoformat(e["publish_at"]) >= hoy and not e.get("skip")][:60]
    media = d / "media"
    muestras = [media_url(cid, f"muestras/{f.name}") for f in sorted((media / "muestras").glob("*.jpg"))] \
        if (media / "muestras").exists() else []
    bib = load(d / "biblioteca" / "index.json", {"fotos": []})["fotos"]
    fotos = [{"id": f.get("id"), "origen": f.get("origen"), "notas": f.get("notas", ""),
              "url": f"/bib/{cid}/{f['archivo']}" if f.get("archivo") and (d / "biblioteca" / f["archivo"]).exists() else None}
             for f in bib]
    lt = []
    for t, v in sorted(tandas.items()):
        pdf = v.get("pdf") or ""
        lt.append({"id": t, **{k: v.get(k) for k in ("estado", "creada", "aprobada", "desde", "hasta", "nota",
                                                    "cambios", "cambios_pedidos", "cambios_hechos")},
                   "n_posts": len([i for i in v.get("posts", []) if not i.startswith("f-")]),
                   "pdf": media_url(cid, Path(pdf).name) if pdf and (media / Path(pdf).name).exists() else None})
    checklist = d / f"CHECKLIST_{cid}.md"
    sin_programar = [{"id": p["id"], "titulo": p.get("title", ""), "ejemplo": bool(p.get("ejemplo"))}
                     for p in posts.values() if p["id"] not in {e["id"] for e in cal}]
    return {**r, "marca": {k: marca.get(k) for k in ("plantillas", "fotos", "pilares", "pilar_pregunta", "logo_texto",
                                                      "adorno", "tono", "contenido_propio", "media_host")},
            "plan": {k: plan.get(k) for k in ("ritmo", "carrusel", "dato", "pregunta", "reels", "tanda", "aprobacion",
                                              "activo", "ensayo")},
            "proximas": proximas, "muestras": muestras,
            "catalogo": media_url(cid, "catalogo.jpg") if (media / "catalogo.jpg").exists() else None,
            "perfil": media_url(cid, "perfil.jpg") if (media / "perfil.jpg").exists() else None,
            "fotos": fotos, "tandas": lt, "sin_programar": sin_programar,
            "checklist": checklist.read_text(encoding="utf-8") if checklist.exists() else "",
            "vista_cliente": f"/c/{cid}"}


def vista_cliente(cid: str) -> dict:
    """Lo que ve el cliente: nada interno, solo su contenido y lo que tiene que decidir."""
    d = cliente_dir(cid)
    marca = load(d / "marca.json", {})
    posts = {p["id"]: p for p in load(d / "content" / "posts.json", {"posts": []})["posts"]}
    reels = {x["id"]: x for x in load(d / "content" / "reels.json", {"reels": []})["reels"]}
    publicados = load(d / "content" / "published.json", {})
    tandas = load(d / "content" / "tandas.json", {})
    pend = [(t, v) for t, v in sorted(tandas.items()) if v.get("estado") == "pendiente"]
    bloqueados = {i for _, v in pend for i in v.get("posts", [])}
    revisar = None
    if pend:
        t, v = pend[0]
        items = [ficha_item(cid, d, e, posts, reels, publicados, bloqueados, n) for n, e in enumerate(items_tanda(d, v), 1)]
        plazo = date.fromisoformat(v.get("revision") or v["creada"]).toordinal() + T.PLAZO - date.today().toordinal()
        revisar = {"tanda": t, "desde": v["desde"], "hasta": v["hasta"], "items": items, "dias_para_aprobar": max(0, plazo),
                   "cambios": v.get("cambios", []),
                   "esperando_cambios": bool(v.get("cambios_pedidos") and not v.get("cambios_hechos"))}
    cal = load(d / "content" / "content_calendar.json", {"posts": []})["posts"]
    hoy = datetime.now().replace(hour=0, minute=0)
    proximas = [ficha_item(cid, d, e, posts, reels, publicados, bloqueados)
                for e in sorted(cal, key=lambda e: e["publish_at"])
                if datetime.fromisoformat(e["publish_at"]) >= hoy and not e["id"].startswith("f-")
                and e["id"] not in bloqueados and not e.get("skip")][:12]
    return {"id": cid, "nombre": marca.get("nombre", cid), "instagram": marca.get("instagram", ""),
            "colores": marca.get("colores", {}),
            "perfil": media_url(cid, "perfil.jpg") if (d / "media" / "perfil.jpg").exists() else None,
            "revisar": revisar, "proximas": proximas}


# ---------------- acciones ----------------
def accion(cid: str, que: str, datos: dict) -> dict:
    d = cliente_dir(cid)
    plan = load(d / "content" / "plan.json", {})
    m = "motor/"
    if que == "muestras":
        pasos = [[m + "muestras.py", "--cliente", cid], [m + "catalogo.py", "--cliente", cid]]
    elif que == "catalogo":
        pasos = [[m + "catalogo.py", "--cliente", cid]]
    elif que == "imagenes":
        pasos = [[m + "render.py", "--cliente", cid], [m + "perfil.py", "--cliente", cid, "15"]]
    elif que == "perfil":
        pasos = [[m + "perfil.py", "--cliente", cid, "15"]]
    elif que == "tanda_ejemplo":
        if plan.get("activo") or not plan.get("ensayo"):
            return {"ok": False, "salida": "La tanda de ejemplo solo es para clientes de ensayo."}
        pasos = [[m + "tanda_ejemplo.py", "--cliente", cid], [m + "tandas.py", "cerrar", "--cliente", cid]]
    elif que == "cerrar_tanda":
        pasos = [[m + "tandas.py", "cerrar", "--cliente", cid]]
    elif que == "aprobar":
        pasos = [[m + "tandas.py", "aprobar", "--cliente", cid]]
    elif que == "rehacer":
        pasos = [[m + "tandas.py", "rehacer", "--cliente", cid]]
    elif que == "simular":
        pasos = [[m + "publish.py", "--cliente", cid, "upcoming", "8"],
                 [m + "publish.py", "--cliente", cid, "run", "--dry-run", "--max", "1"]]
    elif que == "ensayo":
        if plan.get("activo"):
            return {"ok": False, "salida": "Es un cliente activo: no se pasa a ensayo desde el panel."}
        plan["ensayo"] = bool(datos.get("valor", True))
        save(d / "content" / "plan.json", plan)
        return {"ok": True, "salida": f"✓ {cid}: ensayo {'activado' if plan['ensayo'] else 'desactivado'}"}
    else:
        return {"ok": False, "salida": f"Acción desconocida: {que}"}
    salida, ok = [], True
    with LOCK:
        for p in pasos:
            code, out = correr(p)
            salida.append(f"$ python {' '.join(p)}\n{out}")
            if code != 0:
                ok = False
                break
    if que == "simular":
        salida.append(semana_simulada(d))
    return {"ok": ok, "salida": "\n\n".join(salida)}


def semana_simulada(d: Path, dias=7) -> str:
    """Qué saldría los próximos días si el piloto automático siguiera su curso (sin publicar nada)."""
    cal = load(d / "content" / "content_calendar.json", {"posts": []})["posts"]
    publicados = load(d / "content" / "published.json", {})
    tandas = load(d / "content" / "tandas.json", {})
    bloq = {i for v in tandas.values() if v.get("estado") == "pendiente" for i in v.get("posts", [])}
    hoy = date.today()
    L = [f"Próximos {dias} días (simulación; lo «en revisión» no sale hasta que el cliente lo apruebe):"]
    for k in range(dias):
        dia = date.fromordinal(hoy.toordinal() + k)
        es = [e for e in sorted(cal, key=lambda e: e["publish_at"]) if e["publish_at"][:10] == dia.isoformat() and not e.get("skip")]
        if not es:
            continue
        L.append(f"  {dia.strftime('%d/%m')}")
        for e in es:
            marca = "publicada" if e["id"] in publicados else ("en revisión" if e["id"] in bloq else "saldría")
            L.append(f"    {e['publish_at'][11:16]}  {TIPOS.get(e['type'], e['type']):9} {e['id']:14} {marca}")
    return "\n".join(L) if len(L) > 1 else "No hay nada programado en los próximos días."


def accion_global(que: str) -> dict:
    cmds = {"estado": ["motor/tandas.py", "estado"], "tokens": ["motor/tokens.py", "estado"],
            "prueba": ["pruebas/prueba_motor.py"], "simular_todos": ["motor/todos.py", "publicar", "--simular"]}
    if que not in cmds:
        return {"ok": False, "salida": f"Acción desconocida: {que}"}
    with LOCK:
        code, out = correr(cmds[que])
    return {"ok": code == 0, "salida": f"$ python {' '.join(cmds[que])}\n{out}"}


def alta(ficha: dict, forzar=False) -> dict:
    if not isinstance(ficha, dict) or not ficha.get("_marca"):
        return {"ok": False, "salida": "La ficha no trae _marca: genérala con el asistente actualizado."}
    slug = re.sub(r"[^a-z0-9]+", "_", str((ficha.get("_marca") or {}).get("id") or "cliente").lower())[:40]
    tmpdir = Path(tempfile.mkdtemp())
    tmp = tmpdir / f"ficha_{slug}_panel.json"
    tmp.write_text(json.dumps(ficha, ensure_ascii=False), encoding="utf-8")
    try:
        with LOCK:
            code, out = correr(["alta/alta.py", tmp, *(["--forzar"] if forzar else [])])
    finally:
        tmp.unlink(missing_ok=True)
        tmpdir.rmdir()
    cid = (ficha.get("_marca") or {}).get("id")
    m = re.search(r"clientes[/\\]([a-z0-9-]+)", out)
    if m:
        cid = m.group(1)
    return {"ok": code == 0, "salida": out, "cliente": cid}


def subir_foto(cid: str, datos: dict) -> dict:
    d = cliente_dir(cid)
    nombre = re.sub(r"[^\w.-]", "_", datos.get("nombre") or "foto.jpg")[-80:]
    if not nombre.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        return {"ok": False, "salida": "Solo fotos JPG, PNG o WEBP."}
    try:
        crudo = base64.b64decode(datos["datos"].split(",", 1)[-1])
    except (KeyError, ValueError):
        return {"ok": False, "salida": "No he podido leer la foto."}
    if len(crudo) > 25 * 1024 * 1024:
        return {"ok": False, "salida": "La foto pesa más de 25 MB."}
    tmpdir = Path(tempfile.mkdtemp())
    f = tmpdir / nombre
    f.write_bytes(crudo)
    try:
        with LOCK:
            code, out = correr(["motor/biblioteca.py", "--cliente", cid, "añadir", f, "--notas", datos.get("notas", "")])
    finally:
        f.unlink(missing_ok=True)
        tmpdir.rmdir()
    return {"ok": code == 0, "salida": out}


def respuesta_cliente(cid: str, datos: dict) -> dict:
    """El cliente aprueba la tanda o pide cambios por número de publicación."""
    d = cliente_dir(cid)
    p = d / "content" / "tandas.json"
    with LOCK:
        tandas = load(p, {})
        t = datos.get("tanda")
        if t not in tandas or tandas[t].get("estado") != "pendiente":
            return {"ok": False, "salida": "Esa tanda ya no está pendiente de revisar."}
        v = tandas[t]
        hoy = date.today().isoformat()
        if datos.get("accion") == "aprobar":
            v.update(estado="aprobada", aprobada=hoy, nota="aprobada por el cliente")
            save(p, tandas)
            return {"ok": True, "salida": "¡Gracias! Queda aprobada y se publicará en sus fechas."}
        cambios = [c for c in (datos.get("cambios") or []) if str(c.get("texto", "")).strip()]
        if not cambios:
            return {"ok": False, "salida": "Escribe qué cambiarías en al menos una publicación."}
        ronda = 1 + max((c.get("ronda", 1) for c in v.get("cambios", [])), default=0)
        v.setdefault("cambios", []).extend({"n": c.get("n"), "id": c.get("id"), "texto": str(c["texto"]).strip()[:1500],
                                            "fecha": hoy, "ronda": ronda} for c in cambios)
        v.update(cambios_pedidos=hoy, cambios_hechos=None)
        save(p, tandas)
    return {"ok": True, "salida": f"Recibido: {len(cambios)} cambio(s). Te avisamos cuando estén hechos."}


# ---------------- servidor ----------------
class H(BaseHTTPRequestHandler):
    server_version = "PanelIG/1.0"

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            sys.stderr.write("  " + (fmt % args) + "\n")

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, code=200):
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _html(self, nombre, inyectar=""):
        txt = (PANEL / nombre).read_text(encoding="utf-8")
        if inyectar:
            txt = txt.replace("</body>", inyectar + "</body>")
        self._send(200, txt.encode("utf-8"), "text/html; charset=utf-8")

    def _origen_ok(self):
        """Las llamadas que cambian algo solo se aceptan desde el propio panel."""
        o = self.headers.get("Origin") or ""
        host = self.headers.get("Host") or ""
        return not o or urlparse(o).netloc == host

    def do_GET(self):
        u = urlparse(self.path)
        ruta = unquote(u.path)
        try:
            if ruta in ("/", "/index.html"):
                return self._html("panel.html")
            if ruta == "/asistente":
                return self._html("asistente.html", (PANEL / "asistente_puente.html").read_text(encoding="utf-8"))
            if ruta.startswith("/c/"):
                cliente_dir(ruta[3:].strip("/"))
                return self._html("cliente.html")
            if ruta == "/api/clientes":
                return self._json(lista_clientes())
            if ruta.startswith("/api/cliente/"):
                return self._json(detalle(ruta.split("/")[3]))
            if ruta.startswith("/api/c/"):
                return self._json(vista_cliente(ruta.split("/")[3]))
            if ruta.startswith(("/media/", "/bib/")):
                return self._media(ruta)
            self._json({"error": "No encontrado"}, 404)
        except LookupError as e:
            self._json({"error": str(e)}, 404)
        except Exception as e:  # noqa: BLE001
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def _media(self, ruta):
        partes = ruta.split("/", 3)   # '', 'media'|'bib', cid, resto
        cid, resto = partes[2], partes[3] if len(partes) > 3 else ""
        d = cliente_dir(cid)
        base = (d / ("media" if partes[1] == "media" else "biblioteca")).resolve()
        f = (base / resto).resolve()
        if not str(f).startswith(str(base) + os.sep) or not f.is_file():
            return self._json({"error": "No encontrado"}, 404)
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        self._send(200, f.read_bytes(), ctype)

    def do_POST(self):
        if not self._origen_ok():
            return self._json({"error": "Origen no permitido"}, 403)
        n = int(self.headers.get("Content-Length") or 0)
        if n > 40 * 1024 * 1024:
            return self._json({"error": "Demasiado grande"}, 413)
        try:
            datos = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._json({"error": "JSON no válido"}, 400)
        ruta = urlparse(self.path).path
        try:
            if ruta == "/api/alta":
                return self._json(alta(datos.get("ficha"), bool(datos.get("forzar"))))
            if ruta == "/api/global":
                return self._json(accion_global(datos.get("accion", "")))
            if ruta.startswith("/api/cliente/") and ruta.endswith("/accion"):
                return self._json(accion(ruta.split("/")[3], datos.get("accion", ""), datos))
            if ruta.startswith("/api/cliente/") and ruta.endswith("/foto"):
                return self._json(subir_foto(ruta.split("/")[3], datos))
            if ruta.startswith("/api/c/") and ruta.endswith("/respuesta"):
                return self._json(respuesta_cliente(ruta.split("/")[3], datos))
            self._json({"error": "No encontrado"}, 404)
        except LookupError as e:
            self._json({"error": str(e)}, 404)
        except Exception as e:  # noqa: BLE001
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=8765)
    ap.add_argument("--sin-navegador", action="store_true")
    a = ap.parse_args()
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", a.puerto), H)
    except OSError:
        url = f"http://127.0.0.1:{a.puerto}/"
        print(f"El panel ya está abierto (o el puerto {a.puerto} está ocupado): {url}")
        if not a.sin_navegador:
            webbrowser.open(url)
        return
    url = f"http://127.0.0.1:{a.puerto}/"
    print(f"Panel abierto en {url}  (cierra esta ventana para pararlo)")
    if not a.sin_navegador:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

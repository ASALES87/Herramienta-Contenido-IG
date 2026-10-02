"""Prueba completa del motor con un cliente ficticio («Floristería Margarita»), sin tocar los demás clientes.

Uso:  python pruebas/prueba_motor.py [--reel] [--conservar]
  --reel        monta también un reel (necesita ffmpeg; ~1 min)
  --conservar   no borra clientes/prueba-floristeria al terminar (para mirar las imágenes)

Recorre: alta → posts → planificar → imágenes (sin fotos y con fotos) → mosaico sin colores vecinos iguales →
catálogo de plantillas → cuaderno de revisión → tanda pendiente que bloquea la publicación → aprobación →
publicación simulada. Termina con OK / FALLO por cada paso.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CID = "prueba-floristeria"
DIR = ROOT / "clientes" / CID
PY = sys.executable
resultados = []


def paso(nombre, ok, detalle=""):
    resultados.append((nombre, ok, detalle))
    print(f"{'OK   ' if ok else 'FALLO'} {nombre}" + (f" · {detalle}" if detalle else ""))


def sh(*args, cliente=True):
    cmd = [PY, *map(str, args)] + (["--cliente", CID] if cliente else [])
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def ficha():
    pil = {"P1": "Ramos y flores de temporada", "P2": "Detrás del taller", "P3": "Mitos y cuidados",
           "P4": "Bodas y eventos", "P5": "Clientes y momentos", "P6": "Tu turno"}
    marca = {"id": CID, "nombre": "Floristería Margarita", "instagram": "margarita.prueba", "sector": "comercio",
             "colores": {"principal": "#3D5A40", "fondo": "#F7F4EE", "acento": "#D97A8B", "texto": "#1E2620"},
             "fuentes": {"titulo": "Quicksand.ttf", "texto": "Poppins-Regular.ttf", "texto_semi": "Poppins-SemiBold.ttf"},
             "logo": None, "logo_claro": None, "logo_texto": "margarita", "logo_etiqueta": "flores", "adorno": "puntos",
             "plantillas": ["foto_marco", "bloques"], "fotos": {"nivel": "auto", "nivel_max": "mitad"},
             "pilares": pil, "pilar_pregunta": "P6", "destacadas": {k: v.split(" ")[0] for k, v in pil.items()},
             "destacadas_sub": {}, "textos": {}, "cta_por_defecto": "Escríbenos por WhatsApp",
             "video_query_defecto": "florist arranging flowers", "contenido_propio": {"fotos": "algunas", "preferencia": "propias"},
             "media_host": "simulado", "email_avisos": "prueba@ejemplo.invalid"}
    plan = {"activo": False, "ensayo": True, "ritmo": "basico",
            "carrusel": {"dias": ["lunes", "miercoles", "viernes"], "hora": "13:30"}, "dato": {"hora": "08:00"},
            "pregunta": {"activo": True, "dia": "domingo", "hora": "10:00"},
            "reels": {"activo": True, "dias": ["jueves"], "hora": "12:00", "pilares": ["P1", "P2"]},
            "tanda": {"dias_minimos_por_delante": 21, "dias_por_tanda": 35}, "aprobacion": "primera",
            "mosaico": {"activo": True, "secuencia": ["principal", "fondo", "principal", "acento"], "desfase": 0}}
    return {"nombre": marca["nombre"], "actividad": "Floristería de barrio con taller propio", "estrella": "Ramos de temporada",
            "email": "prueba@ejemplo.invalid", "okDatos": True, "okConexion": True, "tieneIG": "si_usa", "fotos": "algunas",
            "_marca": marca, "_plan": plan, "_diagnostico": []}


def posts(prefijo, n, n_preg):
    out = []
    for i in range(1, n + 1):
        out.append({"id": f"{prefijo}-{i:02d}", "pillar": ["P1", "P2", "P3", "P4", "P5"][i % 5],
                    "title": f"Publicación de prueba número {i}",
                    "slides": [{"h": "Primera idea", "body": "Texto de prueba para comprobar que el motor coloca bien el contenido."},
                               {"h": "Segunda idea", "body": "Otro texto de prueba, algo más largo, para ver cómo se ajusta la letra."}],
                    "fact": "Dato de prueba para la diapositiva del medio.", "cta": "¿Te ha gustado la prueba?",
                    "caption": f"Caption de prueba {i} #Prueba", "video_query": "flowers bouquet", "foto_query": "flowers"})
    for j in range(1, n_preg + 1):
        out.append({"id": f"{prefijo}-q{j}", "pillar": "P6", "title": f"Pregunta de prueba {j}", "cta": "¿Qué opinas?",
                    "caption": "Pregunta de prueba"})
    return out


def fotos_sinteticas(carpeta, n):
    from PIL import Image, ImageDraw
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    for i in range(n):
        im = Image.new("RGB", (1200, 1500), (200 - i * 12, 160 + i * 8, 140 + i * 10))
        d = ImageDraw.Draw(im)
        for k in range(6):
            d.ellipse((100 + k * 160, 300 + (k % 2) * 400, 400 + k * 160, 600 + (k % 2) * 400), fill=(220, 90 + k * 20, 120))
        p = carpeta / f"foto_{i}.jpg"
        im.save(p)
        rutas.append(p)
    return rutas


def main():
    reel = "--reel" in sys.argv
    if DIR.exists():
        shutil.rmtree(DIR)
    tmp = ROOT / "pruebas" / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "ficha.json").write_text(json.dumps(ficha(), ensure_ascii=False), encoding="utf-8")
    try:
        rc, out = sh("alta/alta.py", tmp / "ficha.json", "--id", CID, cliente=False)
        paso("Alta desde la ficha", rc == 0 and (DIR / "marca.json").exists(), out.strip().splitlines()[0] if out else "")

        # 1.ª tanda sin fotos → todo color
        (DIR / "content" / "posts.json").write_text(json.dumps({"posts": posts("t1", 12, 4)}, ensure_ascii=False), encoding="utf-8")
        rc, out = sh("motor/planificar.py", "--check")
        paso("Validación de posts", rc == 0, out.strip().splitlines()[-1] if out.strip() else "")
        rc, out = sh("motor/tandas.py", "cerrar", cliente=False) if False else sh("motor/tandas.py", "cerrar")
        paso("Cerrar tanda (planificar + imágenes + perfil + cuaderno)", rc == 0, out.strip().splitlines()[-2] if rc == 0 else out[-300:])
        cal = json.loads((DIR / "content" / "content_calendar.json").read_text(encoding="utf-8"))["posts"]
        car = [e for e in cal if e["type"] == "carousel"]
        hechos = sum(1 for e in car if all((DIR / "media" / "carousels" / e["id"] / f"0{i}.jpg").exists() for i in range(1, 6)))
        paso("Imágenes de todos los carruseles", hechos == len(car), f"{hechos}/{len(car)}")
        pdf = list((DIR / "media").glob("revision_*.pdf"))
        paso("Cuaderno de revisión PDF", bool(pdf), pdf[0].name if pdf else "")

        def vecinos_ok():
            from PIL import Image
            feed = sorted((e for e in cal if e["type"] in ("carousel", "reel")), key=lambda e: e["publish_at"])
            def color(e):
                f = DIR / "media" / ("carousels/" + e["id"] + "/01.jpg" if e["type"] == "carousel" else "reels/" + e["id"] + "_cover.jpg")
                if not f.exists():
                    return None
                im = Image.open(f)
                return im.getpixel((8, im.height // 2))
            cols = [color(e) for e in feed]
            mal = [i for i in range(len(cols)) for j in (i - 1, i - 3) if j >= 0 and cols[i] and cols[i] == cols[j]]
            return not mal, f"{len(cols)} casillas, {len(set(c for c in cols if c))} colores, coincidencias: {mal or 'ninguna'}"
        ok, det = vecinos_ok()
        paso("Mosaico sin colores vecinos iguales (sin fotos)", ok, det)

        # Tanda pendiente bloquea la publicación; al aprobar se desbloquea
        sys.path.insert(0, str(ROOT / "motor"))
        t = json.loads((DIR / "content" / "tandas.json").read_text(encoding="utf-8"))
        pend = [k for k, v in t.items() if v["estado"] == "pendiente"]
        paso("Primera tanda queda pendiente de aprobación", bool(pend), ", ".join(pend))
        code = ("import sys,json,datetime;sys.argv=['x','--cliente','%s'];sys.path.insert(0,'motor');import content_calendar as c;"
                "print(len(c.due_posts(datetime.datetime(2099,1,1,tzinfo=c.tz()))))") % CID
        n_bloq = int(subprocess.run([PY, "-c", code], cwd=ROOT, capture_output=True, text=True).stdout.strip() or -1)
        paso("Nada publicable mientras está pendiente", n_bloq == 0, f"{n_bloq} publicables")
        sh("motor/tandas.py", "aprobar")
        n_ok = int(subprocess.run([PY, "-c", code], cwd=ROOT, capture_output=True, text=True).stdout.strip() or -1)
        paso("Al aprobar, se puede publicar", n_ok > 0, f"{n_ok} publicables")

        # 2.ª tanda con fotos → foto/color según nivel
        for f in fotos_sinteticas(tmp / "fotos", 8):
            sh("motor/biblioteca.py", "añadir", f, "--notas", "flores de prueba")
        p = json.loads((DIR / "content" / "posts.json").read_text(encoding="utf-8"))
        p["posts"] += posts("t2", 9, 3)
        (DIR / "content" / "posts.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        rc, out = sh("motor/tandas.py", "cerrar")
        paso("Segunda tanda con fotos", rc == 0, out.strip().splitlines()[-2] if rc == 0 else out[-300:])
        dis = json.loads((DIR / "content" / "diseno.json").read_text(encoding="utf-8"))
        cal = json.loads((DIR / "content" / "content_calendar.json").read_text(encoding="utf-8"))["posts"]
        nuevos = [e["id"] for e in cal if e["id"].startswith(("t2", "r-t2")) and e["type"] in ("carousel", "reel")]
        con_foto = [i for i in nuevos if dis.get(i, {}).get("plantilla", "").startswith("foto")]
        nv = {dis[i].get("nivel") for i in nuevos if i in dis}
        paso("Con fotos, el feed alterna foto y color según las fotos que hay", 0 < len(con_foto) < len(nuevos),
             f"{len(con_foto)} de {len(nuevos)} con foto · nivel {', '.join(sorted(nv))} con 8 fotos libres")
        ok, det = vecinos_ok()
        paso("Mosaico sin colores vecinos iguales (con fotos)", ok, det)
        rc, out = sh("motor/catalogo.py")
        paso("Catálogo de las 5 plantillas", rc == 0 and (DIR / "media" / "catalogo.jpg").exists())

        # Publicación simulada (media_host «simulado»: no llama a Instagram)
        rc, out = sh("motor/todos.py", "publicar", "--simular")
        paso("Publicación simulada de todos los clientes de ensayo", rc == 0, out.strip().splitlines()[-1] if out.strip() else "")
        rc, out = sh("motor/publish.py", "next")
        paso("Publicar la siguiente en modo simulado", rc == 0 and "[simulado]" in out, out.strip().splitlines()[-1] if out.strip() else "")
        if reel:
            r = [e["id"] for e in cal if e["type"] == "reel"][0]
            rc, out = sh("motor/reels.py", r)
            paso("Montar un reel", rc == 0 and (DIR / "media" / "reels" / f"{r}.mp4").exists(), r)
    finally:
        if "--conservar" not in sys.argv and DIR.exists():
            shutil.rmtree(DIR)
        shutil.rmtree(tmp, ignore_errors=True)
    fallos = [r for r in resultados if not r[1]]
    print(f"\n{len(resultados) - len(fallos)}/{len(resultados)} pasos OK" + (f" · FALLOS: {', '.join(r[0] for r in fallos)}" if fallos else ""))
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()

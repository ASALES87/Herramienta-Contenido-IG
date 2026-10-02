"""Plantillas de publicación. El cliente elige una o varias en marca.json → "plantillas".

  De color (no necesitan fotos):
    bloques        bloques de color de marca con adorno (la de Kodomo)
    tipografica    sobria: título grande, línea de acento, sin adornos
  Con foto (propia de la biblioteca o de stock):
    foto_franja    foto a sangre + franja de color con el título
    foto_completa  foto a sangre con degradado y el título encima
    foto_marco     foto enmarcada sobre color, título debajo

Cuántas publicaciones llevan foto depende de las fotos que tenga el cliente (ver nivel() y PATRONES):
muchas → 3 de cada 4, mitad → tablero foto/color, pocas → 1 de cada 4, ninguna → todo color.
Dentro del carrusel también: con muchas fotos se usan 2 (portada + interior/cierre); con pocas, solo la portada.
Si un post necesita foto y no hay ninguna disponible, se usa la primera plantilla de color (o «bloques»).
Un post puede forzar su plantilla con "plantilla" y su foto con "foto" (id de la biblioteca).
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

import biblioteca as B
import cliente as C
import render as R

W, H, SH, M = R.W, R.H, R.SH, R.M
COLOR = ["bloques", "tipografica"]
FOTO = ["foto_franja", "foto_completa", "foto_marco"]
TODAS = COLOR + FOTO


import json
from datetime import datetime, timedelta

# Cuántas publicaciones del feed llevan foto según las fotos que hay. El patrón se aplica por posición en el
# feed; con 3 columnas cada patrón dibuja una figura ordenada en el perfil:
#   muchas  3 de cada 4 con foto → las de color forman una diagonal
#   mitad   1 de cada 2          → tablero de ajedrez foto / color
#   pocas   1 de cada 4          → las fotos forman una diagonal sobre el color
#   ninguna todo color (con la secuencia de colores de plan.json → mosaico)
PATRONES = {"muchas": [1, 1, 1, 0], "mitad": [1, 0], "pocas": [1, 0, 0, 0], "ninguna": [0]}
NIVELES = ["ninguna", "pocas", "mitad", "muchas"]
FOTOS_POR_CARRUSEL = {"muchas": 2, "mitad": 1, "pocas": 1, "ninguna": 0}
DISENO = C.CONTENT / "diseno.json"   # {item_id: {"plantilla", "nivel"}}: lo ya decidido no cambia


def elegidas() -> list[str]:
    lst = C.MARCA.get("plantillas") or [C.MARCA.get("plantilla") or "bloques"]
    return [t for t in lst if t in TODAS] or ["bloques"]


def _feed():
    R.grid_tone("")  # carga la caché del calendario
    return list(R._grid_cache.keys()) if R._grid_cache else []


def _posicion(item_id: str) -> int:
    orden = _feed()
    return orden.index(item_id) if item_id in orden else 0


_nivel = None


def nivel() -> str:
    """Nivel de fotos para las publicaciones nuevas. marca.json → "fotos": {"nivel": "auto"|muchas|mitad|pocas|ninguna,
    "nivel_max": tope (lo fija el alta según lo que dijo el cliente)}. En «auto» se calcula con las fotos libres
    de la biblioteca frente a las publicaciones del feed de los próximos 35 días."""
    global _nivel
    if _nivel:
        return _nivel
    cfg = C.MARCA.get("fotos") or {}
    tope = cfg.get("nivel_max", "muchas")
    if not any(t in FOTO for t in elegidas()):
        _nivel = "ninguna"
        return _nivel
    forzado = cfg.get("nivel", "auto")
    if forzado != "auto":
        n = forzado
    elif B.stock_permitido():
        n = tope                        # el stock cubre lo que falte
    else:
        try:
            cal = json.loads(C.CAL.read_text(encoding="utf-8"))["posts"]
            hasta = datetime.now() + timedelta(days=35)
            necesita = sum(1 for e in cal if e["type"] in ("carousel", "reel") and not e.get("skip")
                           and datetime.fromisoformat(e["publish_at"]) <= hasta) or 1
        except (OSError, ValueError, KeyError):
            necesita = 20
        hay = len(B.libres())
        r = hay / necesita
        n = "muchas" if r >= 0.75 else "mitad" if r >= 0.5 else "pocas" if hay else "ninguna"
    _nivel = NIVELES[min(NIVELES.index(n), NIVELES.index(tope))]
    return _nivel


def _cargar_diseno():
    try:
        return json.loads(DISENO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _posts_por_item():
    """item del feed → post (los reels desarrollan su carrusel «twin»)."""
    posts = {p["id"]: p for p in json.loads(C.POSTS.read_text(encoding="utf-8"))["posts"]}
    try:
        reels = {r["id"]: r["twin"] for r in json.loads(C.REELS.read_text(encoding="utf-8"))["reels"]}
    except (OSError, ValueError, KeyError):
        reels = {}
    return {iid: posts.get(reels.get(iid, iid)) for iid in _feed()}


_planificado = False


def _planificar_feed():
    """Decide, en orden de publicación, plantilla, fotos y color de cada casilla del feed que aún no lo tenga.
    Con fotos de por medio, el color de cada casilla de color se elige para que no coincida con la anterior
    ni con la de encima (posición −1 y −3 en una cuadrícula de 3 columnas)."""
    global _planificado
    if _planificado:
        return
    _planificado = True
    dis = _cargar_diseno()
    lst = elegidas()
    fotos_t = [t for t in lst if t in FOTO]
    color_t = [t for t in lst if t in COLOR] or ["bloques"]
    feed = _feed()
    por_item = _posts_por_item()
    cambios = False
    for pos, iid in enumerate(feed):
        if iid in dis:
            continue
        p = por_item.get(iid)
        if not p:
            continue
        nv = nivel()
        patron = PATRONES[nv]
        t = p.get("plantilla")
        if not t:
            if fotos_t and patron[pos % len(patron)]:
                n_foto = sum(1 for k in feed[:pos] if dis.get(k, {}).get("plantilla") in FOTO)
                t = fotos_t[n_foto % len(fotos_t)]
            else:   # con dos plantillas de color, se alternan
                n_color = sum(1 for k in feed[:pos] if dis.get(k, {}).get("plantilla") in COLOR)
                t = color_t[n_color % len(color_t)]
        fs = B.asignar_varias(p, max(1, FOTOS_POR_CARRUSEL.get(nv, 1))) if t in FOTO else []
        if t in FOTO and not fs:
            t = color_t[0]
        vec_prev = {dis.get(feed[k], {}).get("tono") for k in (pos - 1, pos - 3) if k >= 0}
        if nv == "ninguna" and R.grid_tone(iid) not in vec_prev:
            tono = R.grid_tone(iid)            # todo color: secuencia de plan.json (como Kodomo), 3 colores
        else:
            vecinos = {dis.get(feed[k], {}).get("tono") for k in (pos - 1, pos - 3) if k >= 0}
            prefer = ["principal", "acento"] if t in FOTO else ["fondo", "principal", "acento"]
            ultimo = next((dis[feed[k]]["tono"] for k in range(pos - 1, -1, -1)
                           if feed[k] in dis and dis[feed[k]]["plantilla"] in COLOR) if t in COLOR else iter(()), None)
            opciones = [c for c in prefer if c not in vecinos] or prefer
            if ultimo in opciones and len(opciones) > 1:
                opciones.remove(ultimo)         # que las casillas de color vayan rotando
            tono = opciones[0]
        dis[iid] = {"plantilla": t, "nivel": nv, "tono": tono}
        cambios = True
    if cambios:
        DISENO.write_text(json.dumps(dis, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def tono(iid: str) -> str:
    _planificar_feed()
    return _cargar_diseno().get(iid, {}).get("tono") or R.grid_tone(iid)


def decidir(p: dict, item_id: str | None = None):
    """(plantilla, fotos, nivel) para un post o un reel. Lo decidido se guarda en content/diseno.json."""
    _planificar_feed()
    iid = item_id or p["id"]
    dis = _cargar_diseno()
    color_t = [t for t in elegidas() if t in COLOR] or ["bloques"]
    if iid in dis:
        t, nv = dis[iid]["plantilla"], dis[iid].get("nivel", "mitad")
    else:   # fuera del feed (p. ej. sin calendario todavía)
        nv, t = nivel(), p.get("plantilla") or color_t[0]
    fs = B.asignar_varias(p, max(1, FOTOS_POR_CARRUSEL.get(nv, 1))) if t in FOTO else []
    if t in FOTO and not fs:
        t = color_t[0]
    return t, fs, nv


# ---------- utilidades ----------

def _oscurecer(img, color, alfa):
    capa = Image.new("RGB", img.size, color)
    return Image.blend(img, capa, alfa)


def _degradado(img, color, desde, hasta, alfa_max=0.88):
    """Degradado vertical de transparente a color (desde/hasta en píxeles)."""
    w, h = img.size
    mask = Image.new("L", (1, h), 0)
    for y in range(h):
        t = 0 if y < desde else min(1, (y - desde) / max(1, hasta - desde))
        mask.putpixel((0, y), int(255 * alfa_max * t))
    mask = mask.resize((w, h))
    return Image.composite(Image.new("RGB", (w, h), color), img, mask)


def _redondear(img, r):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=r, fill=255)
    return mask


def _pie(img, color, pill_bg, pill_fg, y=None):
    d = ImageDraw.Draw(img)
    y = y or H - 160
    R.wordmark(img, M, y - 15, color, pill_bg, pill_fg)
    sf = R.semi_font(30)
    txt = C.texto("desliza")
    d.text((W - M - 62 - d.textlength(txt, font=sf), y), txt, font=sf, fill=color)
    R._arrow_right(d, W - M, y + 21, color)


def _tono_color(tone):
    return {"acento": R.ACENTO, "fondo": R.FONDO}.get(tone, R.PRINCIPAL)


# ---------- portadas ----------

def cover(plantilla, p, foto, tone, alto=H, reel_id=None):
    reel = reel_id is not None
    chip_txt = (f"{C.texto('reel')} · " if reel else "") + R.pillar_name(p["pillar"])
    if plantilla == "bloques" or (plantilla in FOTO and not foto):
        return R._reel_cover_bloques(reel_id, p, tone) if reel else R.slide_cover(p, tone)
    top = 0 if alto == H else 240          # en reels la cuadrícula recorta el centro: margen extra
    if plantilla == "tipografica":
        bg = _tono_color(tone)
        fg = R.legible(bg, R.FONDO, R.TEXTO, "#FFFFFF") if tone != "fondo" else R.TITULO_FONDO
        ac = R.ACENTO if R.contrast(bg, R.ACENTO) > 1.8 else (R.PRINCIPAL if tone != "principal" else R.FONDO)
        img = Image.new("RGB", (W, alto), bg)
        d = ImageDraw.Draw(img)
        sf = R.semi_font(30)
        d.text((M, top + 150), chip_txt.upper(), font=sf, fill=ac)
        d.rectangle((M, top + 205, M + 120, top + 213), fill=ac)
        f, lines, lh = R.fit_text(d, p["title"], R.title_font, W - 2 * M, 760, 124, 66, 1.06)
        R.draw_lines(d, (M, top + 290), lines, f, lh, fg)
        _pie(img, fg, ac, R.legible(ac, R.OSCURO, R.FONDO), y=(alto - 160 - top))
        return img
    if plantilla == "foto_franja":
        img = B.recorte(foto, W, alto)
        franja_y = alto - 560 - top
        bg = _tono_color(tone if tone != "fondo" else "principal")
        fg = R.legible(bg, R.FONDO, R.TEXTO, "#FFFFFF")
        d = ImageDraw.Draw(img)
        d.rectangle((0, franja_y, W, alto), fill=bg)
        R.chip(d, M, franja_y - 34, chip_txt, R.ACENTO if bg != R.ACENTO else R.OSCURO,
               R.legible(R.ACENTO if bg != R.ACENTO else R.OSCURO, R.OSCURO, R.FONDO))
        f, lines, lh = R.fit_text(d, p["title"], R.title_font, W - 2 * M, 300, 88, 54, 1.1)
        R.draw_lines(d, (M, franja_y + 80), lines, f, lh, fg)
        _pie(img, fg, R.ACENTO, R.legible(R.ACENTO, R.OSCURO, R.FONDO), y=alto - 140 - top)
        return img
    if plantilla == "foto_completa":
        img = B.recorte(foto, W, alto)
        img = _degradado(img, R.OSCURO, int(alto * 0.30), int(alto * 0.78))
        d = ImageDraw.Draw(img)
        R.chip(d, M, top + 150, chip_txt, R.ACENTO, R.legible(R.ACENTO, R.OSCURO, R.FONDO))
        f, lines, lh = R.fit_text(d, p["title"], R.title_font, W - 2 * M, 420, 100, 60, 1.08)
        y = alto - 230 - top - lh * len(lines)
        R.draw_lines(d, (M, y), lines, f, lh, "#FFFFFF")
        _pie(img, "#FFFFFF", R.ACENTO, R.legible(R.ACENTO, R.OSCURO, R.FONDO), y=alto - 150 - top)
        return img
    if plantilla == "foto_marco":
        bg = _tono_color(tone)
        fg = R.legible(bg, R.FONDO, R.TEXTO, "#FFFFFF") if tone != "fondo" else R.TITULO_FONDO
        img = Image.new("RGB", (W, alto), bg)
        fh = 720 if alto == H else 900
        ph = B.recorte(foto, W - 2 * M, fh)
        img.paste(ph, (M, top + 110), _redondear(ph, 40))
        d = ImageDraw.Draw(img)
        R.chip(d, M + 30, top + 110 + fh - 40, chip_txt, R.ACENTO, R.legible(R.ACENTO, R.OSCURO, R.FONDO))
        f, lines, lh = R.fit_text(d, p["title"], R.title_font, W - 2 * M, 260, 82, 52, 1.1)
        R.draw_lines(d, (M, top + 110 + fh + 70), lines, f, lh, fg)
        _pie(img, fg, R.ACENTO, R.legible(R.ACENTO, R.OSCURO, R.FONDO), y=alto - 140 - top)
        return img
    raise ValueError(plantilla)


# ---------- interiores ----------

def body(plantilla, p, idx, fotos=(), nivel_="mitad"):
    """Diapositiva interior. Con nivel «muchas» usa la 2.ª foto del post; con «mitad» repite la de portada;
    con «pocas» los interiores van de color (la foto se reserva para la portada)."""
    s = p["slides"][idx - 1]
    fotos = list(fotos or [])
    foto = None if nivel_ == "pocas" else (fotos[1] if len(fotos) > 1 else (fotos[0] if fotos else None))
    if plantilla == "tipografica":
        img = Image.new("RGB", (W, H), R.FONDO)
        d = ImageDraw.Draw(img)
        d.rectangle((M - 40, 240, M - 32, H - 240), fill=R.ACENTO)
        d.text((M, 150), f"{idx:02d}", font=R.semi_font(34), fill=R.ACENTO)
        hf, hl, hlh = R.fit_text(d, s["h"], R.title_font, W - 2 * M, 360, 90, 56, 1.08)
        y = R.draw_lines(d, (M, 260), hl, hf, hlh, R.TITULO_FONDO)
        bf, bl, blh = R.fit_text(d, s["body"], R.body_font, W - 2 * M, 1100 - y, 52, 36, 1.5)
        R.draw_lines(d, (M, y + 60), bl, bf, blh, R.TEXTO)
        R.page_dots(d, idx, 5, R.PRINCIPAL, R.LINEA)
        return img
    usa_foto = foto and ((plantilla == "foto_franja" and idx == 2) or (plantilla == "foto_marco" and idx == 1)
                         or plantilla == "foto_completa")
    if not usa_foto:
        return R.slide_body(p, idx, idx)
    if plantilla == "foto_completa":   # foto difuminada detrás + tarjeta de texto
        img = B.recorte(foto, W, H, dy=0.1 * idx).filter(ImageFilter.GaussianBlur(18))
        img = _oscurecer(img, R.OSCURO, 0.35)
        d = ImageDraw.Draw(img)
        inner = W - 2 * M - 100
        hf, hl, hlh = R.fit_text(d, s["h"], R.title_font, inner, 280, 76, 50, 1.1)
        bf, bl, blh = R.fit_text(d, s["body"], R.body_font, inner, 520, 48, 36, 1.45)
        ch = 150 + hlh * len(hl) + 40 + blh * len(bl) + 60
        y0 = (H - ch) // 2
        d.rounded_rectangle((M, y0, W - M, y0 + ch), radius=44, fill=R.FONDO)
        R.chip(d, M + 50, y0 + 45, str(idx), R.ACENTO, R.legible(R.ACENTO, R.OSCURO, R.FONDO), size=28)
        y = R.draw_lines(d, (M + 50, y0 + 150), hl, hf, hlh, R.TITULO_FONDO)
        R.draw_lines(d, (M + 50, y + 40), bl, bf, blh, R.TEXTO)
        R.page_dots(d, idx, 5, "#FFFFFF", "#9A9A9A")
        return img
    # foto arriba + texto abajo (foto_franja y foto_marco)
    img = Image.new("RGB", (W, H), R.FONDO)
    ph = B.recorte(foto, W - 2 * M, 520, dy=0.12)
    img.paste(ph, (M, 100), _redondear(ph, 36))
    d = ImageDraw.Draw(img)
    hf, hl, hlh = R.fit_text(d, s["h"], R.title_font, W - 2 * M, 200, 72, 50, 1.1)
    y = R.draw_lines(d, (M, 680), hl, hf, hlh, R.TITULO_FONDO)
    d.rounded_rectangle((M, y + 26, M + 90, y + 36), radius=5, fill=R.ACENTO)
    bf, bl, blh = R.fit_text(d, s["body"], R.body_font, W - 2 * M, H - 160 - (y + 70), 46, 34, 1.42)
    R.draw_lines(d, (M, y + 70), bl, bf, blh, R.TEXTO)
    R.page_dots(d, idx, 5, R.PRINCIPAL, R.LINEA)
    return img


def fact(plantilla, p):
    if plantilla != "tipografica":
        return R.slide_fact(p)
    img = Image.new("RGB", (W, H), R.FONDO)
    d = ImageDraw.Draw(img)
    d.text((M, 150), p.get("fact_label", C.texto("dato")).upper(), font=R.semi_font(32), fill=R.ACENTO)
    d.rectangle((M, 205, M + 120, 213), fill=R.ACENTO)
    f, lines, lh = R.fit_text(d, p["fact"], R.title_font, W - 2 * M, 760, 92, 54, 1.14)
    R.draw_lines(d, (M, 300 + max(0, (760 - lh * len(lines)) // 2)), lines, f, lh, R.TITULO_FONDO)
    R.page_dots(d, 3, 5, R.ACENTO, R.LINEA)
    return img


def cta(plantilla, p, fotos=(), nivel_="mitad"):
    """Cierre: con foto (oscurecida) solo cuando hay muchas fotos; si no, el cierre de color."""
    fotos = list(fotos or [])
    foto = fotos[-1] if fotos and nivel_ == "muchas" else None
    if plantilla not in FOTO or not foto:
        return R.slide_cta(p)
    img = _oscurecer(B.recorte(foto, W, H, dy=-0.1), R.OSCURO, 0.78)
    d = ImageDraw.Draw(img)
    f, lines, lh = R.fit_text(d, p["cta"], R.title_font, W - 2 * M, 460, 84, 52, 1.14)
    y = R.draw_lines(d, (M, 360), lines, f, lh, "#FFFFFF")
    sf = R.body_font(38)
    R.draw_lines(d, (M, y + 50), R.wrap(d, p.get("cta_sub", C.texto("cta_sub")), sf, W - 2 * M), sf, 54, "#E8E8E8")
    R.wordmark(img, M, H - 250, "#FFFFFF", R.ACENTO, R.legible(R.ACENTO, R.OSCURO, R.FONDO), size=56)
    if C.usuario():
        d.text((M, H - 160), "@" + C.usuario(), font=R.semi_font(34), fill=R.ACENTO)
    R.page_dots(d, 4, 5, R.ACENTO, "#8A8A8A")
    return img


def story_fact(plantilla, p, foto):
    if plantilla not in FOTO or not foto:
        return R.story_fact(p)
    img = Image.new("RGB", (W, SH), R.ACENTO)
    ph = B.recorte(foto, W, 900)
    img.paste(ph, (0, 0))
    ink = R.legible(R.ACENTO, R.OSCURO, R.FONDO)
    d = ImageDraw.Draw(img)
    R.highlight_tag(d, R.highlight_of(p["pillar"]), "#FFFFFF")
    R.chip(d, M, 860, p.get("fact_label", C.texto("dato")), ink, R.legible(ink, R.FONDO, R.TEXTO), size=32)
    f, lines, lh = R.fit_text(d, p["fact"], R.title_font, W - 2 * M, 480, 84, 52, 1.16)
    R.draw_lines(d, (M, 990), lines, f, lh, ink)
    d.text((M, 1500), C.texto("hoy_en_perfil", hora=R._hora_carrusel()), font=R.semi_font(30), fill=ink)
    R.wordmark(img, 0, SH - 300, ink, R.FONDO, ink, size=44, center=True)
    return img

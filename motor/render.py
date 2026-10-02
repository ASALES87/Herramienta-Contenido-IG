"""Genera las imágenes de marca del cliente a partir de su content/posts.json.

  carrusel   5 diapositivas JPEG 1080x1350 (portada, 2 ideas, dato, cierre)
  historias  1080x1920: «dato» de cada carrusel y «pregunta» (pilar_pregunta de marca.json)
  destacadas portadas para las historias destacadas del perfil

Uso:
  python render.py --cliente demo              -> genera lo que falte
  python render.py --cliente demo --force      -> regenera todo
  python render.py --cliente demo s01-1        -> solo uno (por id)
  python render.py --cliente demo --highlights -> portadas de destacadas

Todo lo que es de la marca (colores, fuentes, logo, @, pilares, textos) sale de clientes/<id>/marca.json.
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import cliente as C

POSTS = C.POSTS
OUT = C.MEDIA / "carousels"
STORIES = C.MEDIA / "stories"
HIGHLIGHTS = C.MEDIA / "highlights"
FONTS_MOTOR = C.MOTOR / "fonts"

W, H = 1080, 1350
SH = 1920
M = 96  # margen


# ---------- colores ----------

def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(v))):02X}" for v in rgb)


def mix(a, b, t):
    """Mezcla a→b (t=0 a, t=1 b)."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex([ra[i] + (rb[i] - ra[i]) * t for i in range(3)])


def _lum(h):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def legible(bg, *opciones):
    """De las opciones, el color con más contraste sobre bg."""
    return max(opciones, key=lambda c: contrast(bg, c))


_col = C.MARCA.get("colores", {})
PRINCIPAL = _col.get("principal", "#2F4858")
FONDO = _col.get("fondo", "#F5F7F7")
ACENTO = _col.get("acento", "#F26419")
TEXTO = _col.get("texto", "#1B2A33")
PRINCIPAL_SUAVE = mix(FONDO, PRINCIPAL, 0.12)
ACENTO_SUAVE = mix(FONDO, ACENTO, 0.28)
LINEA = mix(FONDO, TEXTO, 0.16)
# Tinta de las diapositivas oscuras (cierre): el color de texto si es oscuro; si no, el principal oscurecido
OSCURO = TEXTO if _lum(TEXTO) < 0.08 else mix(PRINCIPAL, "#000000", 0.55)
SOBRE_OSCURO = legible(OSCURO, FONDO, "#FFFFFF")
TITULO_FONDO = legible(FONDO, PRINCIPAL, TEXTO) if contrast(FONDO, PRINCIPAL) < 3 else PRINCIPAL


# ---------- tipografías ----------
FUENTES_DEF = {"titulo": "Quicksand.ttf", "texto": "Poppins-Regular.ttf", "texto_semi": "Poppins-SemiBold.ttf"}
FONT_SOURCES = {
    "Quicksand.ttf": "https://github.com/google/fonts/raw/main/ofl/quicksand/Quicksand%5Bwght%5D.ttf",
    "Poppins-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf",
    "Poppins-Medium.ttf": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf",
    "Poppins-SemiBold.ttf": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-SemiBold.ttf",
}
FALLBACK_BOLD = ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"]
FALLBACK = ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "arial.ttf"]
_warned = set()


def ensure_fonts() -> None:
    """Descarga las tipografías libres del motor si faltan (solo las de FONT_SOURCES)."""
    FONTS_MOTOR.mkdir(exist_ok=True)
    for name, url in FONT_SOURCES.items():
        dest = FONTS_MOTOR / name
        if not dest.exists():
            try:
                urllib.request.urlretrieve(url, dest)
            except Exception as e:
                print(f"  (aviso) no se pudo descargar {name}: {e}")


def _font_path(rol: str) -> Path | None:
    nombre = (C.MARCA.get("fuentes") or {}).get(rol) or FUENTES_DEF[rol]
    for p in (C.DIR / nombre, C.ASSETS / "fonts" / Path(nombre).name, FONTS_MOTOR / Path(nombre).name):
        if p.exists():
            return p
    return None


_cache = {}


def font(rol: str, size: int) -> ImageFont.FreeTypeFont:
    key = (rol, size)
    if key in _cache:
        return _cache[key]
    p = _font_path(rol)
    f = None
    if p:
        f = ImageFont.truetype(str(p), size)
        if rol == "titulo":
            try:  # fuentes variables (p. ej. Quicksand): peso 700
                f.set_variation_by_axes([int((C.MARCA.get("fuentes") or {}).get("peso_titulo", 700))])
            except Exception:
                pass
    else:
        for fb in (FALLBACK_BOLD if rol != "texto" else FALLBACK):
            try:
                f = ImageFont.truetype(fb, size)
                if rol not in _warned:
                    print(f"  (aviso) usando fuente de reserva para «{rol}»")
                    _warned.add(rol)
                break
            except OSError:
                continue
        f = f or ImageFont.load_default()
    _cache[key] = f
    return f


def title_font(size):
    return font("titulo", size)


def body_font(size):
    return font("texto", size)


def semi_font(size):
    return font("texto_semi", size)


# ---------- utilidades de texto ----------

def wrap(draw, text, fnt, max_w):
    lines = []
    for para in text.split("\n"):
        words, cur = para.split(), ""
        for w in words:
            test = (cur + " " + w).strip()
            if draw.textlength(test, font=fnt) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def fit_text(draw, text, font_fn, max_w, max_h, start, minimum, spacing=1.25):
    size = start
    while size >= minimum:
        fnt = font_fn(size)
        lines = wrap(draw, text, fnt, max_w)
        lh = int(size * spacing)
        if lh * len(lines) <= max_h:
            return fnt, lines, lh
        size -= 2
    fnt = font_fn(minimum)
    return fnt, wrap(draw, text, fnt, max_w), int(minimum * spacing)


def draw_lines(draw, xy, lines, fnt, lh, fill):
    x, y = xy
    for ln in lines:
        draw.text((x, y), ln, font=fnt, fill=fill)
        y += lh
    return y


# ---------- elementos de marca ----------

def _logo_img(sobre_oscuro: bool):
    """Logo del cliente (PNG con transparencia). marca.json → logo / logo_claro (versión para fondos oscuros)."""
    rel = C.MARCA.get("logo_claro") if sobre_oscuro and C.MARCA.get("logo_claro") else C.MARCA.get("logo")
    p = C.asset(rel)
    return Image.open(p).convert("RGBA") if p else None


def wordmark(img, x, y, color_text, pill_bg, pill_fg, size=44, center=False):
    """Logo: imagen si existe; si no, el nombre en la tipografía de títulos (+ etiqueta opcional, p. ej. «PLAY»)."""
    d = ImageDraw.Draw(img)
    bg = img.getpixel((min(W - 1, int(x) + 2), min(img.height - 1, int(y) + 2)))
    oscuro = _lum(_hex(bg[:3])) < 0.25
    logo = _logo_img(oscuro)
    if logo:
        h = int(size * 1.5)
        w = int(logo.width * h / logo.height)
        if w > 420:
            w, h = 420, int(logo.height * 420 / logo.width)
        logo = logo.resize((w, h), Image.LANCZOS)
        xx = int((W - w) / 2) if center else int(x)
        img.paste(logo, (xx, int(y)), logo)
        return
    txt = C.MARCA.get("logo_texto") or C.MARCA.get("nombre", "")
    f = title_font(size)
    tw = d.textlength(txt, font=f)
    etiqueta = C.MARCA.get("logo_etiqueta")
    pf = semi_font(int(size * 0.42))
    pw = (d.textlength(etiqueta, font=pf) + 28) if etiqueta else 0
    total = tw + (12 + pw if etiqueta else 0)
    if center:
        x = (W - total) / 2
    d.text((x, y), txt, font=f, fill=color_text)
    if etiqueta:
        ph = int(size * 0.72)
        px, py = x + tw + 12, y + int(size * 0.28)
        d.rounded_rectangle((px, py, px + pw, py + ph), radius=ph // 2, fill=pill_bg)
        d.text((px + 14, py + (ph - pf.size) // 2 - 3), etiqueta, font=pf, fill=pill_fg)


def adorno(draw, x, y, s, colors):
    """Motivo decorativo de la marca (marca.json → "adorno": cubos | puntos | ninguno)."""
    tipo = C.MARCA.get("adorno", "puntos")
    if tipo == "ninguno":
        return
    for i, c in enumerate(colors):
        if tipo == "cubos":
            cx, cy = x + i * int(s * 0.78), y + i * int(s * 0.34)
            draw.rounded_rectangle((cx, cy, cx + s, cy + s), radius=int(s * 0.22), fill=c)
        else:
            r = int(s * 0.32)
            cx, cy = x + int(s * 0.5) + i * int(s * 0.85), y + int(s * 0.5)
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c)


def chip(draw, x, y, text, bg, fg, size=30):
    f = semi_font(size)
    tw = draw.textlength(text.upper(), font=f)
    h = int(size * 1.9)
    draw.rounded_rectangle((x, y, x + tw + 48, y + h), radius=h // 2, fill=bg)
    draw.text((x + 24, y + (h - size) // 2 - 4), text.upper(), font=f, fill=fg)
    return h


def page_dots(draw, idx, total, color_on, color_off):
    r, gap = 9, 30
    x0 = W // 2 - (total - 1) * gap // 2
    for i in range(total):
        cx = x0 + i * gap
        draw.ellipse((cx - r, H - 70 - r, cx + r, H - 70 + r), fill=color_on if i == idx else color_off)


# ---------- mosaico del perfil (tablero de ajedrez) ----------
# Las portadas de carruseles y reels siguen plan.json → mosaico.secuencia (p. ej. principal, fondo, principal, acento):
# con 3 columnas, dos portadas vecinas nunca coinciden de color.
SEQ_DEFAULT = ["principal", "fondo", "principal", "acento"]
_grid_cache = None
_ALIAS = {"verde": "principal", "crema": "fondo", "mostaza": "acento", "light": "fondo"}  # nombres antiguos (Kodomo)


def grid_tone(item_id: str) -> str:
    global _grid_cache
    if _grid_cache is None:
        _grid_cache = {}
        try:
            cal = json.loads(C.CAL.read_text(encoding="utf-8"))["posts"]
            mos = C.plan().get("mosaico", {})
            offset = int(mos.get("desfase", 0))
            feed = sorted((e for e in cal if e["type"] in ("carousel", "reel") and not e.get("skip")),
                          key=lambda e: e["publish_at"])
            seq = mos.get("secuencia") or SEQ_DEFAULT
            for i, e in enumerate(feed):
                _grid_cache[e["id"]] = seq[(i + offset) % len(seq)]
            if mos.get("activo", True) is False:
                _grid_cache = {k: "principal" for k in _grid_cache}
        except (OSError, ValueError, KeyError):
            pass
    t = _grid_cache.get(item_id, "principal")
    return _ALIAS.get(t, t)


def cover_palette(tone):
    tone = _ALIAS.get(tone, tone)
    if tone == "fondo":
        bg = FONDO
        txt = TITULO_FONDO
        return dict(bg=bg, text=txt, chip_bg=PRINCIPAL, chip_fg=legible(PRINCIPAL, FONDO, TEXTO, "#FFFFFF"),
                    deco=[ACENTO, PRINCIPAL, PRINCIPAL_SUAVE], wm_text=txt, wm_pill=ACENTO,
                    wm_pill_fg=legible(ACENTO, TEXTO, FONDO), hint=TEXTO)
    bg = ACENTO if tone == "acento" else PRINCIPAL
    otro = PRINCIPAL if tone == "acento" else ACENTO
    txt = legible(bg, FONDO, TEXTO, "#FFFFFF")
    chip_bg = legible(bg, OSCURO, otro, FONDO) if tone == "acento" else otro
    return dict(bg=bg, text=txt, chip_bg=chip_bg, chip_fg=legible(chip_bg, FONDO, TEXTO, "#FFFFFF"),
                deco=[otro, FONDO, mix(bg, FONDO, 0.35)], wm_text=txt, wm_pill=otro,
                wm_pill_fg=legible(otro, TEXTO, FONDO), hint=txt)


def pillar_name(pid):
    return C.pilares().get(pid, "")


# ---------- diapositivas ----------

def _arrow_right(d, x1, y, color):
    aw = 44
    d.line((x1 - aw, y, x1 - 4, y), fill=color, width=4)
    d.line((x1 - 14, y - 11, x1, y), fill=color, width=4)
    d.line((x1 - 14, y + 11, x1, y), fill=color, width=4)


def slide_cover(p, tone=None):
    c = cover_palette(tone or grid_tone(p["id"]))
    img = Image.new("RGB", (W, H), c["bg"])
    d = ImageDraw.Draw(img)
    adorno(d, W - M - 260, 110, 110, c["deco"])
    chip(d, M, 150, pillar_name(p["pillar"]), c["chip_bg"], c["chip_fg"])
    f, lines, lh = fit_text(d, p["title"], title_font, W - 2 * M, 640, 104, 60, 1.12)
    y = 330 + max(0, (640 - lh * len(lines)) // 2)
    draw_lines(d, (M, y), lines, f, lh, c["text"])
    wordmark(img, M, H - 175, c["wm_text"], c["wm_pill"], c["wm_pill_fg"])
    sf = semi_font(30)
    txt = C.texto("desliza")
    tx = W - M - 44 - 18 - d.textlength(txt, font=sf)
    d.text((tx, H - 160), txt, font=sf, fill=c["hint"])
    _arrow_right(d, W - M, H - 160 + 21, c["hint"])
    return img


def reel_cover(reel_id, p):
    """Portada del reel con la plantilla que le toca (ver plantillas.py)."""
    import plantillas as T
    t, fs, _ = T.decidir(p, reel_id)
    return T.cover(t, p, fs[0] if fs else None, T.tono(reel_id), alto=SH, reel_id=reel_id)


def _reel_cover_bloques(reel_id, p, tone=None):
    """Portada del reel (1080x1920). La cuadrícula recorta el centro, así que todo va en la franja central."""
    c = cover_palette(tone or grid_tone(reel_id))
    img = Image.new("RGB", (W, SH), c["bg"])
    d = ImageDraw.Draw(img)
    adorno(d, W - M - 260, 330, 110, c["deco"])
    chip(d, M, 370, f"{C.texto('reel')} · {pillar_name(p['pillar'])}", c["chip_bg"], c["chip_fg"])
    f, lines, lh = fit_text(d, p["title"], title_font, W - 2 * M, 760, 110, 64, 1.12)
    y = 560 + max(0, (760 - lh * len(lines)) // 2)
    draw_lines(d, (M, y), lines, f, lh, c["text"])
    wordmark(img, M, 1440, c["wm_text"], c["wm_pill"], c["wm_pill_fg"])
    return img


def slide_body(p, idx, n):
    s = p["slides"][idx - 1]
    img = Image.new("RGB", (W, H), FONDO)
    d = ImageDraw.Draw(img)
    d.text((M - 6, 80), f"0{n}", font=title_font(170), fill=ACENTO_SUAVE)
    top, bottom = 300, H - 170
    hf, hl, hlh = fit_text(d, s["h"], title_font, W - 2 * M, 330, 84, 54, 1.12)
    bf, bl, blh = fit_text(d, s["body"], body_font, W - 2 * M, 560, 54, 38, 1.45)
    block = hlh * len(hl) + 110 + blh * len(bl)
    y0 = top + max(0, (bottom - top - block) // 2)
    y = draw_lines(d, (M, y0), hl, hf, hlh, TITULO_FONDO)
    d.rounded_rectangle((M, y + 36, M + 100, y + 48), radius=6, fill=ACENTO)
    draw_lines(d, (M, y + 110), bl, bf, blh, TEXTO)
    page_dots(d, idx, 5, PRINCIPAL, LINEA)
    return img


def slide_fact(p):
    ink = legible(ACENTO, OSCURO, FONDO)
    img = Image.new("RGB", (W, H), ACENTO)
    d = ImageDraw.Draw(img)
    chip(d, M, 150, p.get("fact_label", C.texto("dato")), ink, legible(ink, FONDO, TEXTO))
    d.text((M - 10, 250), "“", font=title_font(260), fill=ink)
    f, lines, lh = fit_text(d, p["fact"], title_font, W - 2 * M, 620, 86, 50, 1.18)
    y = 470 + max(0, (620 - lh * len(lines)) // 2)
    draw_lines(d, (M, y), lines, f, lh, ink)
    page_dots(d, 3, 5, ink, mix(ACENTO, FONDO, 0.4))
    return img


def slide_cta(p):
    img = Image.new("RGB", (W, H), OSCURO)
    d = ImageDraw.Draw(img)
    adorno(d, M, 130, 90, [PRINCIPAL if contrast(OSCURO, PRINCIPAL) > 1.6 else FONDO, ACENTO, FONDO])
    f, lines, lh = fit_text(d, p["cta"], title_font, W - 2 * M, 460, 80, 50, 1.15)
    y = draw_lines(d, (M, 380), lines, f, lh, SOBRE_OSCURO)
    sf = body_font(38)
    sub = p.get("cta_sub", C.texto("cta_sub"))
    draw_lines(d, (M, y + 50), wrap(d, sub, sf, W - 2 * M), sf, 54, mix(OSCURO, SOBRE_OSCURO, 0.75))
    wordmark(img, M, H - 250, SOBRE_OSCURO, ACENTO, legible(ACENTO, OSCURO, FONDO), size=56)
    if C.usuario():
        d.text((M, H - 160), "@" + C.usuario(), font=semi_font(34), fill=ACENTO if contrast(OSCURO, ACENTO) >= 3 else SOBRE_OSCURO)
    page_dots(d, 4, 5, ACENTO, mix(OSCURO, SOBRE_OSCURO, 0.25))
    return img


def render_post(p, force=False):
    folder = OUT / p["id"]
    files = [folder / f"{i:02d}.jpg" for i in range(1, 6)]
    if not force and all(f.exists() for f in files):
        return files
    folder.mkdir(parents=True, exist_ok=True)
    import plantillas as T
    t, fs, nv = T.decidir(p)
    slides = [T.cover(t, p, fs[0] if fs else None, T.tono(p["id"])), T.body(t, p, 1, fs, nv),
              T.body(t, p, 2, fs, nv), T.fact(t, p), T.cta(t, p, fs, nv)]
    print(f"  {p['id']}: plantilla {t}" + (f" · fotos {', '.join(f['id'] for f in fs)} (nivel {nv})" if fs else ""))
    for img, f in zip(slides, files):
        img.save(f, "JPEG", quality=92, optimize=True, progressive=True)
    return files


# ---------- historias ----------

def down_arrow(d, cx, y, color, size=34, width=5):
    d.line((cx, y, cx, y + size), fill=color, width=width)
    d.line((cx - 14, y + size - 14, cx, y + size), fill=color, width=width)
    d.line((cx + 14, y + size - 14, cx, y + size), fill=color, width=width)


def highlight_of(pillar):
    return (C.MARCA.get("destacadas") or {}).get(pillar) or pillar_name(pillar)


def highlight_tag(d, name, color):
    """Etiqueta arriba a la derecha: a qué destacada hay que añadir la historia (la API no lo permite)."""
    if not name:
        return
    f = semi_font(26)
    txt = name.upper()
    tw = d.textlength(txt, font=f)
    x1, y0 = W - M, 296
    d.rounded_rectangle((x1 - tw - 40, y0, x1, y0 + 52), radius=26, outline=color, width=3)
    d.text((x1 - tw - 20, y0 + 9), txt, font=f, fill=color)


def _hora_carrusel():
    return (C.plan().get("carrusel") or {}).get("hora", "20:30")


def story_fact(p):
    ink = legible(ACENTO, OSCURO, FONDO)
    img = Image.new("RGB", (W, SH), ACENTO)
    d = ImageDraw.Draw(img)
    highlight_tag(d, highlight_of(p["pillar"]), ink)
    chip(d, M, 380, p.get("fact_label", C.texto("dato")), ink, legible(ink, FONDO, TEXTO), size=32)
    d.text((M - 10, 470), "“", font=title_font(240), fill=ink)
    f, lines, lh = fit_text(d, p["fact"], title_font, W - 2 * M, 640, 96, 58, 1.16)
    y = 700 + max(0, (640 - lh * len(lines)) // 2)
    draw_lines(d, (M, y), lines, f, lh, ink)
    card_y = 1420
    d.rounded_rectangle((M, card_y, W - M, card_y + 150), radius=36, fill=ink)
    on_ink = legible(ink, FONDO, TEXTO)
    d.text((M + 40, card_y + 26), C.texto("hoy_en_perfil", hora=_hora_carrusel()), font=semi_font(30),
           fill=legible(ink, ACENTO, on_ink) if contrast(ink, ACENTO) > 3 else on_ink)
    tf, tl, _ = fit_text(d, p["title"], title_font, W - 2 * M - 80, 60, 44, 30, 1.1)
    d.text((M + 40, card_y + 72), tl[0] + ("…" if len(tl) > 1 else ""), font=tf, fill=on_ink)
    wordmark(img, 0, SH - 300, ink, FONDO, ink, size=44, center=True)
    return img


def render_fact_story(p, force=False):
    f = STORIES / f"f-{p['id']}.jpg"
    if f.exists() and not force:
        return f
    STORIES.mkdir(parents=True, exist_ok=True)
    import plantillas as T
    t, fs, _ = T.decidir(p)
    T.story_fact(t, p, fs[0] if fs else None).save(f, "JPEG", quality=92, optimize=True, progressive=True)
    return f


def story_question(p):
    """Historia «pregunta a la comunidad». Zonas seguras: nada importante en los 250 px de arriba ni en los 340 de abajo."""
    bg = PRINCIPAL
    on = legible(bg, FONDO, TEXTO, "#FFFFFF")
    img = Image.new("RGB", (W, SH), bg)
    d = ImageDraw.Draw(img)
    highlight_tag(d, highlight_of(p["pillar"]) or C.texto("pregunta"), on)
    chip(d, M, 290, C.texto("pregunta"), ACENTO, legible(ACENTO, OSCURO, FONDO), size=32)
    tf, tl, tlh = fit_text(d, p["title"], title_font, W - 2 * M, 470, 100, 62, 1.12)
    y = draw_lines(d, (M, 470), tl, tf, tlh, on)
    contexto = (p.get("slides") or [{}])[0].get("body") or p.get("contexto") or ""
    if contexto:
        cf, cl, clh = fit_text(d, contexto, body_font, W - 2 * M, 260, 42, 32, 1.45)
        y = draw_lines(d, (M, y + 40), cl, cf, clh, mix(bg, on, 0.85))
    q = p.get("cta") or p["title"]
    qf, ql, qlh = fit_text(d, q, title_font, W - 2 * M - 96, 300, 66, 44, 1.15)
    card_h = qlh * len(ql) + 96
    cy = max(y + 60, 1380 - card_h)
    d.rounded_rectangle((M, cy, W - M, cy + card_h), radius=40, fill=FONDO)
    draw_lines(d, (M + 48, cy + 48), ql, qf, qlh, TEXTO)
    sf = semi_font(38)
    txt = C.texto("responde")
    ty = cy + card_h + 50
    d.text(((W - d.textlength(txt, font=sf)) / 2, ty), txt, font=sf, fill=on)
    down_arrow(d, W // 2, ty + 62, ACENTO)
    wordmark(img, 0, SH - 300, on, ACENTO, legible(ACENTO, OSCURO, FONDO), size=44, center=True)
    return img


def render_story(p, force=False):
    f = STORIES / f"{p['id']}.jpg"
    if f.exists() and not force:
        return f
    STORIES.mkdir(parents=True, exist_ok=True)
    story_question(p).save(f, "JPEG", quality=92, optimize=True, progressive=True)
    return f


def render_highlights():
    """Portadas para las destacadas (se suben a mano: perfil > destacada > editar portada).
    Una por cada nombre distinto en marca.json → destacadas (subtítulo opcional en destacadas_sub)."""
    HIGHLIGHTS.mkdir(parents=True, exist_ok=True)
    nombres = list(dict.fromkeys((C.MARCA.get("destacadas") or {}).values()))
    subs = C.MARCA.get("destacadas_sub") or {}
    tonos = [(PRINCIPAL, legible(PRINCIPAL, FONDO, TEXTO)), (ACENTO, legible(ACENTO, OSCURO, FONDO)),
             (OSCURO, SOBRE_OSCURO), (FONDO, TITULO_FONDO)]
    out = []
    for i, word in enumerate(nombres):
        bg, fg = tonos[i % len(tonos)]
        img = Image.new("RGB", (W, SH), bg)
        d = ImageDraw.Draw(img)
        r = 330
        cx, cy = W // 2, SH // 2
        ring = ACENTO if contrast(bg, ACENTO) > 1.5 else OSCURO
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ring, width=14)
        tf, tl, tlh = fit_text(d, word, title_font, 2 * r - 180, 260, 140, 70, 1.05)
        y = cy - (tlh * len(tl)) // 2 - (30 if subs.get(word) else 0)
        for ln in tl:
            d.text((cx - d.textlength(ln, font=tf) / 2, y), ln, font=tf, fill=fg)
            y += tlh
        if subs.get(word):
            sf = semi_font(40)
            d.text((cx - d.textlength(subs[word], font=sf) / 2, y + 10), subs[word], font=sf, fill=fg)
        slug = "".join(ch if ch.isalnum() else "-" for ch in word.lower()).strip("-")
        f = HIGHLIGHTS / f"destacada_{slug}.jpg"
        img.save(f, "JPEG", quality=92)
        out.append(f)
    return out


def es_pregunta(p):
    return p.get("pillar") == C.pilar_pregunta()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--highlights", action="store_true", help="genera las portadas de destacadas")
    a = ap.parse_args()
    ensure_fonts()
    if a.highlights:
        for f in render_highlights():
            print(f"✓ {f.name}")
        return
    posts = json.loads(POSTS.read_text(encoding="utf-8"))["posts"]
    if a.ids:
        posts = [p for p in posts if p["id"] in a.ids]
    n_c = n_s = 0
    for p in posts:
        force = a.force or bool(a.ids)
        if es_pregunta(p):
            render_story(p, force=force); n_s += 1
        else:
            render_post(p, force=force); n_c += 1
            render_fact_story(p, force=force); n_s += 1
        print(f"✓ {p['id']}")
    print(f"[{C.ID}] {n_c} carruseles en {OUT} · {n_s} historias en {STORIES}")


if __name__ == "__main__":
    sys.exit(main())

"""Genera los reels del cliente (vídeo vertical 1080x1920, 30 s, H.264 + AAC).

Cada reel desarrolla el contenido de una publicación de la semana (content/reels.json):
  el del domingo, la del lunes; el del martes, la del miércoles.
  0-4 s      gancho (título) desde el primer fotograma, sobre el vídeo nítido
  3-3,9      el vídeo se difumina y sigue corriendo detrás
  4-20,5     las dos ideas, con su explicación
  20,5-25,5  el dato destacado
  25,5-30    cierre: logo + la pregunta para comentar

Fondo: vídeo de stock de Pixabay (PIXABAY_API_KEY) o Pexels (PEXELS_API_KEY), gratis; si no hay, una foto
de la biblioteca con movimiento lento; si tampoco, el color de marca. Un vídeo propio en clientes/<id>/media/reels_src/<id del carrusel>.mp4 (tiene prioridad).
Cada reel busca su propio vídeo con la búsqueda de reels.json y nunca repite uno ya usado
(content/videos_usados.json).
Música: los .mp3 de clientes/<id>/assets/music/ (o, si no hay, motor/assets/music/) van rotando en orden de publicación. Si no hay, va sin música.

Uso:  python reels.py --cliente demo r-s01-1        (genera clientes/demo/media/reels/r-s01-1.mp4)
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
from PIL import Image, ImageDraw

import cliente as C
import render as R

REELS_JSON = C.REELS
OUT = C.MEDIA / "reels"
SRC = C.MEDIA / "reels_src"
MUSIC = C.ASSETS / "music" if any((C.ASSETS / "music").glob("*.mp3")) else C.MOTOR / "assets" / "music"
USED_VIDEOS = C.CONTENT / "videos_usados.json"   # reel → vídeo de stock usado (para no repetir)
W, H, DUR = 1080, 1920, 30.0
INTRO = 3.0   # segundos de vídeo nítido (con el gancho encima) antes de difuminarse
# gancho (desde el segundo 0) · idea 1 · idea 2 · dato · cierre (logo + pregunta)
BEATS = [(0.0, 4.0), (4.0, 12.3), (12.3, 20.5), (20.5, 25.5), (25.5, DUR)]


# ---------- fondo ----------

def _used_videos() -> dict:
    try:
        return json.loads(USED_VIDEOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _mark_video(reel_id: str, url: str):
    used = _used_videos()
    used[reel_id] = url
    USED_VIDEOS.write_text(json.dumps(used, ensure_ascii=False, indent=1), encoding="utf-8")


def pexels_video(query: str, dest: Path, avoid: set = frozenset()) -> str | None:
    key = C.secreto("PEXELS_API_KEY")
    if not key:
        return None
    r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": key},
                     params={"query": query, "orientation": "portrait", "per_page": 15, "size": "medium"}, timeout=30)
    r.raise_for_status()
    for v in r.json().get("videos", []):
        if v.get("duration", 0) < 6 or v.get("url") in avoid:
            continue
        files = [f for f in v["video_files"] if f.get("file_type") == "video/mp4"
                 and (f.get("height") or 0) >= 1280 and (f.get("height") or 0) > (f.get("width") or 0)]
        if not files:
            continue
        best = sorted(files, key=lambda f: abs((f.get("height") or 0) - 1920))[0]
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(best["link"], stream=True, timeout=120) as dl:
            dl.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in dl.iter_content(1 << 20):
                    fh.write(chunk)
        (dest.with_suffix(".txt")).write_text(f"Pexels: {v.get('url')} · autor: {v.get('user', {}).get('name')}\n", encoding="utf-8")
        print(f"  ↓ Fondo de Pexels: {v.get('url')}")
        return v.get("url")
    print(f"  (aviso) Pexels no encontró vídeo vertical para «{query}»")
    return None


def pixabay_video(query: str, dest: Path, avoid: set = frozenset()) -> str | None:
    """Alternativa gratuita a Pexels (licencia de Pixabay). Muchos vídeos son horizontales:
    se recorta el centro a 9:16, así que se prefieren los de mayor resolución."""
    key = C.secreto("PIXABAY_API_KEY")
    if not key:
        return None
    r = requests.get("https://pixabay.com/api/videos/", params={"key": key, "q": query, "video_type": "film",
                     "safesearch": "true", "per_page": 20}, timeout=30)
    r.raise_for_status()
    best = None
    for hit in r.json().get("hits", []):
        if hit.get("duration", 0) < 6 or hit.get("pageURL") in avoid:
            continue
        for size in ("large", "medium"):
            v = hit.get("videos", {}).get(size) or {}
            w, h = v.get("width") or 0, v.get("height") or 0
            if not v.get("url") or h < 1080:
                continue
            # alto útil tras recortar a 9:16 (cuanto más, mejor nitidez)
            useful = h if h > w else min(h, int(w * 16 / 9))
            score = useful + (2000 if h > w else 0)  # preferir verticales
            if not best or score > best[0]:
                best = (score, v["url"], hit.get("pageURL"))
            break
    if not best:
        print(f"  (aviso) Pixabay no encontró vídeo para «{query}»")
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(best[1], stream=True, timeout=180) as dl:
        dl.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in dl.iter_content(1 << 20):
                fh.write(chunk)
    dest.with_suffix(".txt").write_text(f"Pixabay: {best[2]}\n", encoding="utf-8")
    print(f"  ↓ Fondo de Pixabay: {best[2]}")
    return best[2] or str(dest)


def pick_music(reel_id: str, reels: list) -> Path | None:
    """Rota las pistas en orden: 1.er reel → pista 1, 2.º → pista 2… y vuelta a empezar."""
    tracks = sorted(MUSIC.glob("*.mp3")) if MUSIC.exists() else []
    if not tracks:
        return None
    order = [r["id"] for r in sorted(reels, key=lambda r: r["publish_at"])]
    pos = order.index(reel_id) if reel_id in order else int(hashlib.md5(reel_id.encode()).hexdigest(), 16)
    return tracks[pos % len(tracks)]


# ---------- capas de texto (PNG transparentes) ----------

def _panel(text, font_fn, start, minimum, bg, fg, y_center=1180, width=W - 2 * R.M):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f, lines, lh = R.fit_text(d, text, font_fn, width - 100, 520, start, minimum, 1.15)
    h = lh * len(lines) + 100
    y0 = y_center - h // 2
    d.rounded_rectangle((R.M, y0, R.M + width, y0 + h), radius=44, fill=bg)
    R.draw_lines(d, (R.M + 50, y0 + 50), lines, f, lh, fg)
    return img


def _hex(c, a=255):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def _card(heading, body, y_center=1150, num=None):
    """Tarjeta de color fondo con titular y texto de desarrollo (legible en 6-7 s)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    inner = W - 2 * R.M - 100
    hf, hl, hlh = R.fit_text(d, heading, R.title_font, inner, 260, 70, 50, 1.12)
    bf, bl, blh = R.fit_text(d, body, R.body_font, inner, 520, 46, 36, 1.42)
    top_pad = 50 + (90 if num else 0)
    h = top_pad + hlh * len(hl) + 40 + blh * len(bl) + 60
    y0 = y_center - h // 2
    d.rounded_rectangle((R.M, y0, W - R.M, y0 + h), radius=44, fill=_hex(R.FONDO, 245))
    if num:
        R.chip(d, R.M + 50, y0 + 40, num, R.ACENTO, R.legible(R.ACENTO, R.OSCURO, R.FONDO), size=28)
    y = R.draw_lines(d, (R.M + 50, y0 + top_pad), hl, hf, hlh, R.TITULO_FONDO)
    R.draw_lines(d, (R.M + 50, y + 40), bl, bf, blh, R.TEXTO)
    return img


def layers(post: dict) -> list[Image.Image]:
    """Desarrolla el contenido del carrusel: gancho, dos ideas explicadas, dato y pregunta final."""
    on_p = R.legible(R.PRINCIPAL, R.FONDO, R.TEXTO, "#FFFFFF")
    hook = _panel(post["title"], R.title_font, 100, 60, _hex(R.PRINCIPAL, 240), on_p, y_center=1000)
    a = _card(post["slides"][0]["h"], post["slides"][0]["body"], num="1")
    b = _card(post["slides"][1]["h"], post["slides"][1]["body"], num="2")
    fact = _panel(post["fact"], R.title_font, 72, 46, _hex(R.ACENTO, 245), R.legible(R.ACENTO, R.OSCURO, R.FONDO))
    end = Image.new("RGBA", (W, H), _hex(R.PRINCIPAL, 238))  # deja intuir el vídeo detrás
    d = ImageDraw.Draw(end)
    R.adorno(d, (W - 300) // 2, 520, 120, [R.ACENTO, R.FONDO, R.mix(R.PRINCIPAL, R.FONDO, 0.35)])
    f, lines, lh = R.fit_text(d, post["cta"], R.title_font, W - 2 * R.M, 360, 84, 54, 1.12)
    y = 820
    for ln in lines:
        d.text(((W - d.textlength(ln, font=f)) / 2, y), ln, font=f, fill=on_p)
        y += lh
    sf = R.semi_font(40)
    sub = C.texto("comenta")
    d.text(((W - d.textlength(sub, font=sf)) / 2, y + 40), sub, font=sf, fill=R.mix(R.PRINCIPAL, on_p, 0.85))
    R.wordmark(end, 0, 1460, on_p, R.ACENTO, R.legible(R.ACENTO, R.OSCURO, R.FONDO), size=56, center=True)
    if C.usuario():
        hf = R.semi_font(40)
        at = "@" + C.usuario()
        col = R.ACENTO if R.contrast(R.PRINCIPAL, R.ACENTO) > 2.2 else on_p
        d.text(((W - d.textlength(at, font=hf)) / 2, 1560), at, font=hf, fill=col)
    # marca de agua discreta durante todo el vídeo (zona segura superior)
    wm = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    R.wordmark(wm, R.M, 260, "#FFFFFF", R.ACENTO, R.legible(R.ACENTO, R.OSCURO, R.FONDO), size=40)
    return [wm, hook, a, b, fact, end]


# ---------- montaje ----------

def cover(reel_id: str) -> Path:
    """Portada del reel para la cuadrícula del perfil (tono según el mosaico de ajedrez)."""
    reels = {r["id"]: r for r in json.loads(REELS_JSON.read_text(encoding="utf-8"))["reels"]}
    posts = {p["id"]: p for p in json.loads(R.POSTS.read_text(encoding="utf-8"))["posts"]}
    R.ensure_fonts()
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{reel_id}_cover.jpg"
    R.reel_cover(reel_id, posts[reels[reel_id]["twin"]]).save(f, "JPEG", quality=92, optimize=True)
    return f


def build(reel_id: str, force: bool = False) -> Path:
    reel_list = json.loads(REELS_JSON.read_text(encoding="utf-8"))["reels"]
    reels = {r["id"]: r for r in reel_list}
    reel = reels[reel_id]
    posts = {p["id"]: p for p in json.loads(R.POSTS.read_text(encoding="utf-8"))["posts"]}
    post = posts[reel["twin"]]
    out = OUT / f"{reel_id}.mp4"
    if out.exists() and not force:
        return out
    OUT.mkdir(parents=True, exist_ok=True)
    R.ensure_fonts()

    bg = SRC / f"{reel['twin']}.mp4"
    if not bg.exists():
        dest = SRC / f"{reel['twin']}.mp4"
        used = _used_videos()
        avoid = {u for rid, u in used.items() if rid != reel_id}
        mine = used.get(reel_id)
        url = pexels_video(reel["query"], dest, avoid) or pixabay_video(reel["query"], dest, avoid)
        bg = dest if url else None
        if url and url != mine:
            _mark_video(reel_id, url)
    foto = None
    if not bg:   # sin vídeo: foto de la biblioteca con movimiento lento; y si tampoco hay, color de marca
        try:
            import biblioteca as B
            f = B.asignar(post) if B.fotos() or B.stock_permitido() else None
            if f:
                foto = B.ruta(f)
                print(f"  (aviso) sin vídeo: fondo con la foto {f['id']} en movimiento")
        except Exception as e:
            print(f"  (aviso) no se pudo usar una foto de fondo: {e}")
        if not foto:
            print("  (aviso) sin vídeo ni foto: fondo de color de marca")
    music = pick_music(reel_id, reel_list)
    if music:
        print(f"  ♪ Música: {music.name}")

    with tempfile.TemporaryDirectory() as tmp:
        pngs = []
        for i, im in enumerate(layers(post)):
            p = Path(tmp) / f"l{i}.png"
            im.save(p)
            pngs.append(p)

        cmd = ["ffmpeg", "-y", "-loglevel", "error"]
        if bg:
            cmd += ["-stream_loop", "-1", "-i", str(bg)]
            # vídeo nítido al principio; a los INTRO s se difumina y oscurece y sigue corriendo detrás del texto
            base = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                    f"fps=30,trim=0:{DUR},setpts=PTS-STARTPTS,split[clear][blur0];"
                    f"[blur0]boxblur=22:2,eq=brightness=-0.10:saturation=0.85,format=yuva420p,"
                    f"fade=t=in:st={INTRO}:d=0.9:alpha=1[blurf];"
                    f"[clear][blurf]overlay=0:0,format=yuv420p[bg]")
        elif foto:
            cmd += ["-loop", "1", "-framerate", "30", "-t", str(DUR), "-i", str(foto)]
            zw, zh = int(W * 1.15), int(H * 1.15)
            base = (f"[0:v]scale={zw}:{zh}:force_original_aspect_ratio=increase,crop={zw}:{zh},"
                    f"crop={W}:{H}:x='(iw-ow)/2':y='(ih-oh)*t/{DUR}',"
                    f"fps=30,trim=0:{DUR},setpts=PTS-STARTPTS,split[clear][blur0];"
                    f"[blur0]boxblur=22:2,eq=brightness=-0.10:saturation=0.85,format=yuva420p,"
                    f"fade=t=in:st={INTRO}:d=0.9:alpha=1[blurf];"
                    f"[clear][blurf]overlay=0:0,format=yuv420p[bg]")
        else:
            cmd += ["-f", "lavfi", "-i", f"color=c=0x{R.PRINCIPAL.lstrip('#')}:s={W}x{H}:r=30:d={DUR}"]
            base = f"[0:v]trim=0:{DUR},setpts=PTS-STARTPTS[bg]"
        for p in pngs:
            cmd += ["-loop", "1", "-t", str(DUR), "-i", str(p)]
        if music:
            cmd += ["-i", str(music)]
        else:
            cmd += ["-f", "lavfi", "-t", str(DUR), "-i", "anullsrc=r=48000:cl=stereo"]

        filters = [base]
        prev = "bg"
        # capa 1 = marca de agua (todo el vídeo salvo el cierre)
        filters.append(f"[1:v]format=rgba[wm];[{prev}][wm]overlay=0:0:enable='between(t,0,{BEATS[4][0]})'[v0]")
        prev = "v0"
        for k, (a, b) in enumerate(BEATS):
            idx = k + 2
            if k == 0:   # gancho: visible desde el primer fotograma (sin fundido de entrada)
                fade = f"[{idx}:v]format=rgba,fade=t=out:st={b - 0.3}:d=0.3:alpha=1[t{k}]"
            elif k < 4:
                fade = (f"[{idx}:v]format=rgba,fade=t=in:st={a}:d=0.35:alpha=1,"
                        f"fade=t=out:st={max(a, b - 0.3)}:d=0.3:alpha=1[t{k}]")
            else:
                fade = f"[{idx}:v]format=rgba,fade=t=in:st={a}:d=0.4:alpha=1[t{k}]"
            filters.append(fade)
            filters.append(f"[{prev}][t{k}]overlay=0:0:enable='between(t,{a},{b})'[v{k + 1}]")
            prev = f"v{k + 1}"
        a_idx = len(pngs) + 1
        filters.append(f"[{a_idx}:a]atrim=0:{DUR},asetpts=PTS-STARTPTS,afade=t=in:d=0.8,"
                       f"afade=t=out:st={DUR - 1.5}:d=1.5,volume=0.8[aud]")
        cmd += ["-filter_complex", ";".join(filters), "-map", f"[{prev}]", "-map", "[aud]",
                "-t", str(DUR), "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
                "-preset", "medium", "-b:v", "6M", "-maxrate", "8M", "-bufsize", "12M",
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-movflags", "+faststart", str(out)]
        subprocess.run(cmd, check=True)
    cover(reel_id)
    print(f"✓ Reel generado: {out.name}" + ("" if music else " (sin música: añade .mp3 en assets/music del cliente)"))
    return out


if __name__ == "__main__":
    ids = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not ids:
        print(__doc__)
        sys.exit(1)
    for i in ids:
        build(i, force=True)

"""Publicador — publica en el Instagram del cliente activo desde la línea de comandos.

Todos los comandos llevan --cliente <id> (o la variable CLIENTE).

Uso:
  python publish.py test                       Comprueba que el token funciona
  python publish.py token-status               Días que le quedan al token
  python publish.py refresh-token              Renueva el token 60 días más
  python publish.py photo  media/foto.jpg  --caption "Texto"
  python publish.py reel   media/video.mp4 --caption "Texto"
  python publish.py carousel media/1.png media/2.png ... --caption "Texto"
  python publish.py photo-url https://... --caption "Texto"   (URL ya pública)
  python publish.py run [--dry-run] [--max 1]  Publica lo pendiente del calendario (solo si plan.json → "activo": true)
                                               Lo que llega más de plan.json → retraso_max_horas tarde pasa al
                                               siguiente hueco libre (content/reprogramados.json) y se avisa.
  python publish.py upcoming [10]              Muestra las próximas publicaciones
  python publish.py next                       Publica YA la siguiente pendiente (prueba)
"""
import argparse
import sys
from datetime import date
from pathlib import Path

import cliente as C
import config
import content_calendar as cal
import instagram_api as ig


def _upload(paths, prefix=None):
    import media_host
    urls = []
    for p in paths:
        p = Path(p)
        name = f"{prefix}_{p.name}" if prefix else p.name  # p. ej. s01-2_01.jpg
        print(f"  ↑ Subiendo {name} ({config.MEDIA_HOST})...")
        urls.append(media_host.upload_file(p, filename=name))
    return urls


def _publish(kind, paths, caption, prefix=None):
    urls = _upload(paths, prefix)
    if config.MEDIA_HOST == "simulado":   # pruebas: no se llama a Instagram
        print(f"  [simulado] {kind} con {len(urls)} archivo(s) · caption de {len(caption)} caracteres")
        return None, ""
    if kind == "story":
        mid = ig.publish_story(urls[0])
        print(f"  ✓ Historia publicada (id {mid})")
        return mid, ""
    if kind == "photo":
        mid = ig.publish_photo(urls[0], caption)
    elif kind == "reel":
        mid = ig.publish_reel(urls[0], caption, cover_url=urls[1] if len(urls) > 1 else None)
    elif kind == "carousel":
        mid = ig.publish_carousel(urls, caption)
    else:
        raise ValueError(f"Tipo desconocido: {kind}")
    link = ig.permalink(mid)
    print(f"  ✓ Publicado: {link or mid}")
    return mid, link


def _ensure_media(p):
    """Los reels se montan justo antes de publicarse (fondo de Pexels + textos + música)."""
    if p["type"] == "reel":
        import reels
        f = config.MEDIA_DIR / p["files"][0]
        if not f.exists():
            print(f"  🎬 Montando {p['id']}...")
            reels.build(p["id"])
        c = f.with_name(f"{p['id']}_cover.jpg")
        if not c.exists():
            reels.cover(p["id"])
        return cal.resolve_media(p) + [c]   # vídeo + portada (tono del mosaico)
    return cal.resolve_media(p)


def cmd_test(_):
    info = ig.whoami()
    print(f"OK — conectado como @{info.get('username')} ({info.get('account_type')}), "
          f"{info.get('media_count')} publicaciones.")


def cmd_token_status(_):
    if not config.IG_TOKEN_EXPIRES:
        print("No hay fecha de caducidad guardada en el .env")
        return
    left = (date.fromisoformat(config.IG_TOKEN_EXPIRES) - date.today()).days
    print(f"El token caduca el {config.IG_TOKEN_EXPIRES} (quedan {left} días).")
    if left < 10:
        print("⚠ Renueva ya:  python publish.py refresh-token")


def cmd_refresh(args):
    res = ig.refresh_token()
    if args.out:  # GitHub Actions: se guarda en un archivo temporal, nunca en el log
        Path(args.out).write_text(res["token"], encoding="utf-8")
        Path(args.out + ".expires").write_text(res["expires"], encoding="utf-8")
    print(f"Token renovado. Nueva caducidad: {res['expires']}")


def cmd_next(args):
    """Publica YA la siguiente publicación pendiente del calendario (para probar)."""
    if C.MARCA.get("solo_referencia"):
        print(f"[{C.ID}] Cliente de referencia: nunca se publica desde este repo.")
        return
    nxt = cal.due_posts() or cal.upcoming(1)  # primero las atrasadas
    if not nxt:
        print("No quedan publicaciones pendientes.")
        return
    p = nxt[0]
    print(f"→ Publicando ahora {p['id']} (estaba programada para {p['publish_at']})")
    mid, link = _publish(p["type"], _ensure_media(p), p.get("caption", ""), p["id"])
    if mid:
        cal.mark_published(p["id"], mid, link)


def cmd_upcoming(args):
    for p in cal.upcoming(args.n):
        print(f"{p['publish_at']}  {p['type']:8}  {p['id']:8}  {(p.get('caption') or p.get('title',''))[:60].splitlines()[0]}")


def cmd_media(args):
    _publish(args.kind, args.files, args.caption)


def cmd_photo_url(args):
    mid = ig.publish_photo(args.url, args.caption)
    print(f"✓ Publicado: {ig.permalink(mid) or mid}")


def cmd_run(args):
    if not args.dry_run and not C.activo():
        print(f"[{C.ID}] Cliente inactivo (plan.json → \"activo\": false): no se publica nada.")
        return
    for c in cal.reprogramar_atrasados(persist=not args.dry_run):   # no publicar fuera de hora
        print(f"⚠ {c['id']} ({c['type']}) llega {c['retraso_h']} h tarde (debía salir el {c['antes'].replace('T', ' ')}): "
              f"{'se pasaría' if args.dry_run else 'pasa'} al siguiente hueco libre → {c['ahora'].replace('T', ' ')}")
    posts = cal.due_posts()
    if not posts:
        print("Nada pendiente de publicar.")
        return
    if args.max:
        if len(posts) > args.max:
            print(f"Hay {len(posts)} pendientes; publico {args.max} y dejo el resto para la siguiente ejecución.")
        posts = posts[: args.max]
    failed = 0
    for p in posts:
        print(f"→ {p['id']} ({p['type']}, {p['publish_at']})")
        if args.dry_run:
            print(f"  [dry-run] {p['type']}")
            continue
        try:
            files = _ensure_media(p)
            mid, link = _publish(p["type"], files, p.get("caption", ""), p["id"])
            if mid:
                cal.mark_published(p["id"], mid, link)
        except Exception as e:  # sigue con el resto
            failed += 1
            print(f"  ✗ Error: {e}")
    if failed:
        raise RuntimeError(f"{failed} publicación(es) fallidas")


def main():
    ap = argparse.ArgumentParser(description=f"Publicador · cliente {C.ID}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("test").set_defaults(fn=cmd_test)
    sub.add_parser("token-status").set_defaults(fn=cmd_token_status)
    sp = sub.add_parser("refresh-token")
    sp.add_argument("--out", help="(CI) guardar el token nuevo en este archivo")
    sp.set_defaults(fn=cmd_refresh)
    sub.add_parser("next").set_defaults(fn=cmd_next)
    sp = sub.add_parser("upcoming")
    sp.add_argument("n", nargs="?", type=int, default=10)
    sp.set_defaults(fn=cmd_upcoming)
    for kind in ("photo", "reel", "carousel"):
        sp = sub.add_parser(kind)
        sp.add_argument("files", nargs="+")
        sp.add_argument("--caption", default="")
        sp.set_defaults(fn=cmd_media, kind=kind)
    sp = sub.add_parser("photo-url")
    sp.add_argument("url")
    sp.add_argument("--caption", default="")
    sp.set_defaults(fn=cmd_photo_url)
    sp = sub.add_parser("run")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--max", type=int, default=0, help="máximo de publicaciones en esta ejecución")
    sp.set_defaults(fn=cmd_run)

    args = ap.parse_args()
    try:
        args.fn(args)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

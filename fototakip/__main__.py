"""Komut satırı: python -m fototakip [--port 8080] [--data ~/fototakip-data]"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
import threading

from . import __version__, db, images
from .server import Config, make_server


def lan_addresses() -> list[str]:
    addrs = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        addrs.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(a for a in addrs if not a.startswith("127."))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="fototakip", description="FotoTakip sunucusu")
    p.add_argument("--host", default=os.environ.get("FOTOTAKIP_HOST", "0.0.0.0"))
    p.add_argument("--port", type=int, default=int(os.environ.get("FOTOTAKIP_PORT", "8080")))
    p.add_argument("--data", default=os.environ.get("FOTOTAKIP_DATA", os.path.expanduser("~/fototakip-data")),
                   help="Veritabanı ve fotoğrafların klasörü")
    p.add_argument("--max-upload-mb", type=int, default=int(os.environ.get("FOTOTAKIP_MAX_UPLOAD_MB", "15")))
    p.add_argument("--no-demo", action="store_true", help=argparse.SUPPRESS)  # eski betikler için; artık örnek veri yok
    p.add_argument("--quiet", action="store_true", help="İstek kayıtlarını yazma")
    p.add_argument("--geocoder", default=os.environ.get("FOTOTAKIP_GEOCODER", "on"),
                   help="Fotoğraf koordinatından adres bulma: on (OpenStreetMap), off ya da https://…/reverse")
    p.add_argument("--geocoder-contact", default=os.environ.get("FOTOTAKIP_GEOCODER_CONTACT", ""),
                   help="Nominatim'e gönderilen iletişim e-postası (isteğe bağlı)")
    p.add_argument("--version", action="version", version=f"FotoTakip {__version__}")
    args = p.parse_args(argv)

    cfg = Config(host=args.host, port=args.port, data_dir=os.path.abspath(os.path.expanduser(args.data)),
                 max_upload_mb=args.max_upload_mb, quiet=args.quiet,
                 geocoder=args.geocoder, geocoder_contact=args.geocoder_contact)
    try:
        server = make_server(cfg)
    except OSError as e:
        print(f"Sunucu başlatılamadı ({cfg.host}:{cfg.port}): {e}", file=sys.stderr)
        print("Port kullanımdaysa başka port dene: fototakip --port 8081", file=sys.stderr)
        return 1

    setup_code = ""
    if db.is_empty(cfg.db_path):
        from .api import new_setup_code, setup_code_file
        con = db.connect(cfg.db_path)
        try:
            setup_code = new_setup_code(con)
        finally:
            con.close()
        path = setup_code_file(cfg)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(setup_code + "\n")

    con = db.connect(cfg.db_path)
    try:
        if db.setting(con, "tunnel_autostart", "0") == "1" and db.setting(con, "tunnel_mode", "off") != "off":
            from .api import ApiError, start_tunnel
            try:
                start_tunnel(con, cfg, server.tunnel)
                print("Dışarıdan erişim tüneli başlatılıyor; adres Profil › Entegrasyonlar ekranında görünecek.")
            except ApiError as e:
                print(f"Tünel başlatılmadı: {e.message}")
    finally:
        con.close()

    print(f"FotoTakip {__version__} çalışıyor")
    print(f"  Bu telefonda:   http://localhost:{cfg.port}")
    for a in lan_addresses():
        print(f"  Aynı Wi-Fi'de:  http://{a}:{cfg.port}   (kamera/çevrimdışı için HTTPS tünel gerekir, README'ye bak)")
    print(f"  Veri klasörü:   {cfg.data_dir}")
    print(f"  Adres bulma:    {'açık (OpenStreetMap Nominatim)' if server.geo.enabled else 'kapalı'}")
    if not images.HAVE_PIL:
        print("  Uyarı: Pillow yok; fotoğraflar küçültülmeden saklanacak. Kur: pkg install python-pillow")
    if setup_code:
        print()
        print("  İLK KURULUM: tarayıcıda adresi aç, yönetici hesabını oluştur.")
        print(f"  Kurulum kodu:   {setup_code}")
        print(f"  (Kod ayrıca {setup_code_file(cfg)} dosyasında; kurulum bitince silinir.)")
    print("Durdurmak için Ctrl+C\n", flush=True)

    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stopping.set()
        server.server_close()
        print("FotoTakip durdu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

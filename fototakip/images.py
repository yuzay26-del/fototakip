"""Fotoğraf alma: tür doğrulama, EXIF okuma, yön düzeltme, küçük resim.

EXIF (çekim zamanı + GPS) saf Python ile okunur. Pillow varsa fotoğraf döndürülür,
2560 px'e küçültülür ve EXIF'siz yeniden kaydedilir; dosyada konum kalmaz,
konum yalnızca veritabanında tutulur. Pillow yoksa orijinal dosya saklanır.
"""

from __future__ import annotations

import io
import os
import struct
from datetime import datetime

FULL_EDGE = 2560
THUMB_EDGE = 640
MAX_PIXELS = 60_000_000

try:  # Termux: pkg install python-pillow
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    HAVE_PIL = True
except Exception:  # pragma: no cover - Pillow'suz kurulum
    Image = ImageOps = None
    HAVE_PIL = False


class ImageError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def sniff(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"mif1", b"msf1", b"heim", b"hevc"):
        return "heic"
    return None


# ---------- EXIF ----------

_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}


def _parse_tiff(t: bytes) -> dict:
    if len(t) < 8:
        return {}
    endian = {b"II": "<", b"MM": ">"}.get(t[:2])
    if not endian:
        return {}

    def u16(o):
        return struct.unpack(endian + "H", t[o:o + 2])[0]

    def u32(o):
        return struct.unpack(endian + "I", t[o:o + 4])[0]

    def ifd(off: int) -> dict:
        out: dict = {}
        if off <= 0 or off + 2 > len(t):
            return out
        n = u16(off)
        for k in range(min(n, 512)):
            e = off + 2 + k * 12
            if e + 12 > len(t):
                break
            tag, typ, cnt = u16(e), u16(e + 2), u32(e + 4)
            size = _TYPE_SIZE.get(typ, 0) * cnt
            if size == 0 or size > 65536:
                continue
            voff = e + 8 if size <= 4 else u32(e + 8)
            if voff + size > len(t):
                continue
            raw = t[voff:voff + size]
            if typ == 2:
                val = raw.split(b"\x00")[0].decode("ascii", "replace").strip()
            elif typ == 3:
                val = [struct.unpack(endian + "H", raw[j:j + 2])[0] for j in range(0, size, 2)]
            elif typ == 4:
                val = [struct.unpack(endian + "I", raw[j:j + 4])[0] for j in range(0, size, 4)]
            elif typ in (5, 10):
                fmt = "II" if typ == 5 else "ii"
                val = []
                for j in range(0, size, 8):
                    a, b = struct.unpack(endian + fmt, raw[j:j + 8])
                    val.append(a / b if b else 0.0)
            else:
                val = raw
            out[tag] = val
        return out

    try:
        ifd0 = ifd(u32(4))
        res: dict = {}
        if 0x0112 in ifd0:
            res["orientation"] = ifd0[0x0112][0]
        exif = ifd(ifd0[0x8769][0]) if 0x8769 in ifd0 else {}
        dt = exif.get(0x9003) or exif.get(0x9004) or ifd0.get(0x0132)
        offset = exif.get(0x9011) or exif.get(0x9010)
        if isinstance(dt, str):
            try:
                parsed = datetime.strptime(dt[:19], "%Y:%m:%d %H:%M:%S")
                iso = parsed.isoformat()
                if isinstance(offset, str) and len(offset) == 6 and offset[0] in "+-":
                    iso += offset
                res["taken_at"] = iso
            except ValueError:
                pass
        if 0x8825 in ifd0:
            g = ifd(ifd0[0x8825][0])
            lat, lng = _dms(g.get(2)), _dms(g.get(4))
            if lat is not None and lng is not None and not (lat == 0 and lng == 0):
                if str(g.get(1, "N")).upper().startswith("S"):
                    lat = -lat
                if str(g.get(3, "E")).upper().startswith("W"):
                    lng = -lng
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    res["lat"], res["lng"] = round(lat, 6), round(lng, 6)
        return res
    except (struct.error, IndexError, KeyError, TypeError):
        return {}


def _dms(v) -> float | None:
    if not isinstance(v, list) or len(v) < 3:
        return None
    return v[0] + v[1] / 60 + v[2] / 3600


def read_exif(data: bytes) -> dict:
    """JPEG içindeki APP1/Exif bloğunu bulur ve çözümler."""
    if data[:2] != b"\xff\xd8":
        return {}
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker in (0xD9, 0xDA):
            break
        seglen = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker == 0xE1 and data[i + 4:i + 10] == b"Exif\x00\x00":
            return _parse_tiff(data[i + 10:i + 2 + seglen])
        i += 2 + seglen
    return {}


# ---------- kaydetme ----------

def store(data: bytes, photos_dir: str, photo_id: str) -> dict:
    kind = sniff(data)
    if kind == "heic":
        raise ImageError(
            "heic_unsupported",
            "HEIC/HEIF fotoğraflar desteklenmiyor. Kamera ayarlarında 'Yüksek verimli resimler' seçeneğini kapat.",
        )
    if kind is None:
        raise ImageError("unsupported_type", "Yalnızca JPEG, PNG veya WebP fotoğraf yüklenebilir.")
    meta = read_exif(data) if kind == "jpeg" else {}
    os.makedirs(photos_dir, exist_ok=True)

    if HAVE_PIL:
        try:
            im = Image.open(io.BytesIO(data))
            im = ImageOps.exif_transpose(im)
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            elif im.mode != "RGB":
                im = im.convert("RGB")
        except Exception as exc:  # bozuk dosya, piksel bombası
            raise ImageError("bad_image", f"Fotoğraf açılamadı: {exc.__class__.__name__}") from exc
        full = im.copy()
        full.thumbnail((FULL_EDGE, FULL_EDGE))
        thumb = im.copy()
        thumb.thumbnail((THUMB_EDGE, THUMB_EDGE))
        full_name, thumb_name = f"{photo_id}.jpg", f"{photo_id}_t.jpg"
        full.save(os.path.join(photos_dir, full_name), "JPEG", quality=85, optimize=True)
        thumb.save(os.path.join(photos_dir, thumb_name), "JPEG", quality=78, optimize=True)
        return {"path": full_name, "thumb_path": thumb_name, "mime": "image/jpeg",
                "width": full.width, "height": full.height, **meta}

    ext = {"jpeg": "jpg", "png": "png", "webp": "webp"}[kind]
    name = f"{photo_id}.{ext}"
    with open(os.path.join(photos_dir, name), "wb") as f:
        f.write(data)
    return {"path": name, "thumb_path": name, "mime": f"image/{kind}", "width": None, "height": None, **meta}

"""AI-assisted photo review for FotoTakip (optional OpenAI vision integration).

This module does not make approval decisions. It returns observations and confidence
notes for a human reviewer. Needs an OpenAI API key (set from the app's settings screen
or OPENAI_API_KEY) and network access only when used.

Gizlilik: fotoğraf OpenAI'ye gönderilmeden önce EXIF/konum bilgisi silinir.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from .images import strip_jpeg_metadata

DEFAULT_MODEL = "gpt-4.1-mini"
API_URL = os.environ.get("FOTOTAKIP_AI_URL", "https://api.openai.com/v1/responses")
MAX_BYTES = 8 * 1024 * 1024
LEVELS = {"info", "attention", "critical", "uncertain"}
QUALITIES = {"good", "limited", "poor"}

PROMPT = (
    "FotoTakip saha fotoğrafı için görsel kalite ve işçilik gözlemi yap. "
    "Yalnızca görüntüde gerçekten seçilebilen unsurları belirt; görünmeyen detayları "
    "varsayma. Elektrik/telekom tesisatı ise yalnızca görsel olarak doğrulanabilen "
    "düzen, etiketleme, görünür hasar, açıkta kalan parçalar ve fotoğraf kalitesini "
    "incele. Elektrik güvenliği, standart uygunluğu veya bağlantının enerjisiz/güvenli "
    "olduğunu fotoğraftan kesin doğrulama. Emin olmadığında 'belirsiz' de. "
    "Çıktı Türkçe ve JSON olsun: summary (string), observations (array of {level: "
    "info|attention|critical|uncertain, title, detail}), photo_quality (good|limited|poor), "
    "limitations (array), human_review_required (boolean). İnsan incelemesi zorunlu."
)


class ReviewError(RuntimeError):
    """Safe, user-displayable AI review error."""


def _text_list(value, limit: int, size: int) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(x)[:size] for x in value[:limit] if str(x).strip()]


def normalize(result) -> dict:
    """Normalize untrusted model output to a narrow, predictable schema."""
    if not isinstance(result, dict):
        raise ReviewError("AI yanıtı beklenen biçimde değil.")
    observations = []
    raw_obs = result.get("observations")
    for item in (raw_obs if isinstance(raw_obs, list) else [])[:20]:
        if not isinstance(item, dict):
            continue
        level = item.get("level")
        observations.append({
            "level": level if level in LEVELS else "uncertain",
            "title": str(item.get("title") or "Gözlem")[:120],
            "detail": str(item.get("detail") or "")[:700],
        })
    quality = result.get("photo_quality")
    return {
        "summary": str(result.get("summary") or "Analiz tamamlandı.")[:1000],
        "observations": observations,
        "photo_quality": quality if quality in QUALITIES else "limited",
        "limitations": _text_list(result.get("limitations"), 10, 300),
        "human_review_required": True,  # modelin ne dediğinden bağımsız: karar her zaman insanda
    }


def review_photo(path: str | Path, mime: str, context: str = "", *, api_key: str = "",
                 model: str = "", timeout: float = 45) -> dict:
    """Analyze one image and return structured observations (never an approval verdict)."""
    key = (api_key or os.environ.get("OPENAI_API_KEY", "")).strip()
    if not key:
        raise ReviewError("AI inceleme yapılandırılmamış: Yönetim › Sistem'den OpenAI anahtarını gir.")
    model = (model or os.environ.get("FOTOTAKIP_AI_MODEL") or DEFAULT_MODEL).strip()

    mime = (mime or "").lower()
    if mime == "image/svg+xml":
        raise ReviewError("SVG çizimler incelenemez; gerçek bir fotoğraf çek.")
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise ReviewError("AI inceleme yalnızca JPEG, PNG veya WebP fotoğrafları destekler.")

    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise ReviewError("Fotoğraf okunamadı.") from exc
    if mime == "image/jpeg":
        data = strip_jpeg_metadata(data)  # Pillow'suz kurulumda dosyada konum kalmış olabilir
    if len(data) > MAX_BYTES:
        raise ReviewError("Fotoğraf AI inceleme için çok büyük.")
    image_data = base64.b64encode(data).decode("ascii")

    prompt = PROMPT
    if context:
        prompt += "\nİş bağlamı (kanıt olarak kabul etme): " + context[:1000]

    payload = {
        "model": model,
        "input": [{
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": f"data:{mime};base64,{image_data}"},
            ],
        }],
        "text": {"format": {"type": "json_object"}},
    }
    req = urllib.request.Request(
        os.environ.get("FOTOTAKIP_AI_URL", API_URL),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Never expose provider response bodies or secrets in the UI/log.
        if exc.code in (401, 403):
            raise ReviewError("AI API anahtarı geçersiz veya yetkisiz.") from exc
        if exc.code == 429:
            raise ReviewError("AI kullanım limiti aşıldı; daha sonra tekrar deneyin.") from exc
        raise ReviewError(f"AI servisi yanıt vermedi (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ReviewError("AI servisine bağlanılamadı veya zaman aşımı oldu.") from exc
    except ValueError as exc:
        raise ReviewError("AI yanıtı okunamadı.") from exc

    text = ""
    output = raw.get("output") if isinstance(raw, dict) else None
    for item in output if isinstance(output, list) else []:
        content = item.get("content") if isinstance(item, dict) else None
        for part in content if isinstance(content, list) else []:
            if isinstance(part, dict) and part.get("type") in ("output_text", "text"):
                text += str(part.get("text", ""))
    if not text and isinstance(raw, dict) and isinstance(raw.get("output_text"), str):
        text = raw["output_text"]
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReviewError("AI yanıtı geçerli JSON değil.") from exc

    out = normalize(result)
    out["model"] = model
    return out

"""Gizli ayarlar: OpenAI anahtarı, Cloudflare tünel token'ı.

Veritabanında değil, veri klasöründe yalnızca sahibinin okuyabildiği (0600) ayrı bir dosyada
tutulur. Yedek zip'ine girmez ve istemciye hiçbir zaman gönderilmez; arayüz yalnızca son
4 karakteri görür.
"""

from __future__ import annotations

import json
import os
import threading

_LOCK = threading.Lock()


def _path(data_dir: str) -> str:
    return os.path.join(data_dir, "secrets.json")


def load(data_dir: str) -> dict:
    try:
        with open(_path(data_dir), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get(data_dir: str, key: str) -> str:
    return str(load(data_dir).get(key) or "")


def put(data_dir: str, key: str, value: str | None) -> None:
    with _LOCK:
        data = load(data_dir)
        if value:
            data[key] = value
        else:
            data.pop(key, None)
        path = _path(data_dir)
        tmp = path + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
        os.chmod(path, 0o600)


def hint(value: str) -> str:
    return f"…{value[-4:]}" if value else ""

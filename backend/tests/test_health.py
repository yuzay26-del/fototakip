import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.mark.parametrize("mode", ["termux", "server"])
def test_health_ayardaki_modu_dondurur(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setenv("APP_MODE", mode)
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        response = client.get("/health")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": mode}


def test_kodda_mod_dallanmasi_yok() -> None:
    """Mod adı yalnızca config.py'de geçebilir (AGENTS.md kuralı)."""
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[1] / "app"
    yasak = ('== "termux"', '== "server"', "== 'termux'", "== 'server'")
    ihlaller = [
        str(path)
        for path in app_dir.rglob("*.py")
        if path.name != "config.py" and any(k in path.read_text("utf-8") for k in yasak)
    ]
    assert ihlaller == []

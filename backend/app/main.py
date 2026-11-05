from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.core.config import get_settings


class HealthResponse(BaseModel):
    status: str
    mode: str


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="FotoTakip", version="0.1.0")

    @app.get("/health", response_model=HealthResponse, tags=["sistem"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", mode=settings.app_mode)

    # Derlenmiş arayüz varsa aynı adresten sunulur. Bu karar moda değil,
    # WEB_DIST ayarına bağlıdır.
    if settings.web_dist is not None and settings.web_dist.is_dir():
        app.mount("/", StaticFiles(directory=settings.web_dist, html=True), name="web")

    return app


app = create_app()

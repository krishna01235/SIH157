from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="NIGRANI-SA API", docs_url=None, redoc_url=None)

    @app.get("/health", include_in_schema=False)
    def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "environment": settings.app_env})

    return app


app = create_app()

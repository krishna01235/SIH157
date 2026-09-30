import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.assessment import router as assessment_router
from app.api.demo import router as demo_router
from app.api.review import router as review_router
from app.api.submissions import router as submission_router
from app.config import get_settings
from app.data.database import get_engine
from app.errors import AppError

logger = logging.getLogger("sat_sa")


def error_response(request: Request, error: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message,
                           "details": error.details, "request_id": request.state.request_id}},
    )


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    app = FastAPI(title="NIGRANI-SA API", docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
    app.include_router(submission_router)
    app.include_router(assessment_router)
    app.include_router(demo_router)
    app.include_router(review_router)

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = str(uuid4())
        if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and origin not in settings.allowed_origin_list:
                return error_response(request, AppError("origin_not_allowed", "Request origin is not allowed.", 403))
            if request.headers.get("sec-fetch-site") == "cross-site":
                return error_response(request, AppError("cross_site_request", "Cross-site request is not allowed.", 403))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, error: AppError) -> JSONResponse:
        return error_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def request_error(request: Request, error: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
            for item in error.errors()[:100]
        ]
        return error_response(request, AppError("invalid_request", "Fix the highlighted request fields.", 422, details))

    @app.get("/health", include_in_schema=False)
    def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "environment": settings.app_env})

    @app.get("/ready", include_in_schema=False)
    def ready() -> JSONResponse:
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT version_num FROM alembic_version"))
            return JSONResponse({"status": "ready"})
        except SQLAlchemyError:
            return JSONResponse({"status": "unavailable"}, status_code=503)

    return app


app = create_app()

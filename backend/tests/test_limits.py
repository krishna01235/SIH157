from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.limits import RequestSizeLimit
from app.main import create_app


def test_request_limit_rejects_claimed_and_streamed_bodies():
    app = FastAPI()

    @app.post("/consume")
    async def consume(request: Request) -> dict:
        return {"size": len(await request.body())}

    app.add_middleware(RequestSizeLimit, max_bytes=32)
    with TestClient(app) as client:
        assert client.post("/consume", content=b"x" * 32).json() == {"size": 32}
        claimed = client.post("/consume", content=b"x" * 33)
        assert claimed.status_code == 413
        assert claimed.json()["error"]["code"] == "request_too_large"
        streamed = client.post("/consume", content=iter([b"x" * 20, b"y" * 20]))
        assert streamed.status_code == 413
        assert streamed.json()["error"]["code"] == "request_too_large"


def test_cross_origin_writes_and_unexpected_errors_use_safe_envelopes():
    app = create_app()

    @app.get("/raise-for-test")
    def fail() -> None:
        raise RuntimeError("private diagnostic")

    with TestClient(app, base_url="http://localhost", raise_server_exceptions=False) as client:
        blocked = client.post(
            "/api/v1/entities", json={"name": "Test"},
            headers={"Origin": "https://external.example"},
        )
        assert blocked.status_code == 403
        assert blocked.json()["error"]["code"] == "origin_not_allowed"
        assert blocked.headers["x-request-id"]
        blocked_fetch = client.post(
            "/api/v1/entities", json={"name": "Test"},
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        assert blocked_fetch.status_code == 403
        failed = client.get("/raise-for-test")
        assert failed.status_code == 500
        assert failed.json()["error"]["code"] == "internal_error"
        assert "private diagnostic" not in failed.text

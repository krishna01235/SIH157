from uuid import uuid4

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestTooLarge(Exception):
    pass


class RequestSizeLimit:
    """Bound the HTTP envelope before multipart parsing, including chunked uploads."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        claimed = headers.get(b"content-length")
        if claimed is not None:
            try:
                if int(claimed) > self.max_bytes:
                    await self._reject(scope, send)
                    return
            except ValueError:
                pass

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise RequestTooLarge()
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestTooLarge:
            if response_started:
                raise
            await self._reject(scope, send)

    @staticmethod
    async def _reject(scope: Scope, send: Send) -> None:
        request_id = str(uuid4())
        response = JSONResponse(
            status_code=413,
            content={"error": {"code": "request_too_large", "message": "Request exceeds the size limit.",
                               "details": [], "request_id": request_id}},
            headers={"X-Request-ID": request_id},
        )
        await response(scope, _empty_receive, send)


async def _empty_receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}

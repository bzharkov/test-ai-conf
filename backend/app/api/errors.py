from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, extra: dict | None = None) -> None:
        self.status, self.code, self.message, self.extra = status, code, message, extra or {}


def _resp(status: int, code: str, message: str, extra: dict | None = None) -> JSONResponse:
    body = {"error": {"code": code, "message": message, **(extra or {})}}
    return JSONResponse(status_code=status, content=body)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, exc: ApiError):
        return _resp(exc.status, exc.code, exc.message, exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", [])[1:])
        return _resp(422, "validation_error", f"{loc}: {first.get('msg', 'invalid request')}")

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return _resp(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def _any(_: Request, exc: Exception):
        return _resp(500, "internal_error", "Внутренняя ошибка сервера")

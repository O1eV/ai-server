from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import LayaError
from app.core.logging_config import logger


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning("%s %s -> 검증 실패: %d건", request.method, request.url.path, len(exc.errors()))
        return JSONResponse(
            status_code=422,
            content={"code": "validation_error", "detail": exc.errors()},
        )

    @app.exception_handler(LayaError)
    async def laya_error_handler(request: Request, exc: LayaError) -> JSONResponse:
        log = logger.error if exc.status_code >= 500 else logger.warning
        log(
            "%s %s -> %s %d: %s",
            request.method,
            request.url.path,
            type(exc).__name__,
            exc.status_code,
            exc,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "detail": str(exc)},
        )

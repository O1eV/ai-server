from __future__ import annotations

from fastapi import FastAPI

from app.api import iter_routers
from app.core.config import API_PREFIX, APP_NAME, APP_VERSION
from app.core.handlers import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.logging_config import setup_logging

setup_logging()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan,
)

register_exception_handlers(app)

for router in iter_routers():
    app.include_router(router, prefix=API_PREFIX)


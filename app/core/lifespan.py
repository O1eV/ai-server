from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.core.config import APP_NAME, APP_VERSION, get_settings
from app.core.logging_config import logger
from app.core.model_loader import load_model_bundle
from common.contract import warmup_state


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info(
        "%s %s 시작 (device=%s, model=%s)",
        APP_NAME,
        APP_VERSION,
        settings.device,
        settings.model_path,
    )

    app.state.model_bundle = None
    bundle = load_model_bundle()
    app.state.model_bundle = bundle

    if settings.warmup:
        try:
            bundle.agent.predict(warmup_state(settings.interval), bundle.questions)
            logger.info("예열 완료")
        except Exception:
            logger.warning("예열 실패(무시하고 계속)", exc_info=True)

    logger.info("준비 완료: %s (%s)", bundle.model_path, bundle.device)
    try:
        yield
    finally:
        app.state.model_bundle = None
        logger.info("%s 종료", APP_NAME)

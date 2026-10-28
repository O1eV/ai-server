from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core import lifespan as lifespan_module
from app.core.config import get_settings
from app.core.model_loader import ModelBundle
from app.main import app
from app.services import warmup as warmup_module
from app.services.warmup import build_warmup_candles, run_warmup
from common.contract import NUM_CANDLES


@pytest.fixture(autouse=True)
def _enable_warmup(
    _warmup_off_by_default: Iterator[None], monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """conftest의 기본 OFF를 이 모듈에 한해 되돌린다 (의존성을 명시해 순서를 고정)."""
    monkeypatch.setenv("LAYA_WARMUP", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _boom(*args: object, **kwargs: object) -> dict:
    raise RuntimeError("추론 실패")


def test_build_warmup_candles_has_enough_valid_candles() -> None:
    candles = build_warmup_candles()

    assert len(candles) == NUM_CANDLES
    assert len(candles) >= 15
    assert all(candle.close > 0 for candle in candles)
    assert all(candle.bar_time for candle in candles)


def test_build_warmup_candles_bar_times_are_increasing() -> None:
    candles = build_warmup_candles()

    times = [candle.bar_time for candle in candles]
    assert times == sorted(times)


def test_run_warmup_calls_predict_once(model_bundle: ModelBundle) -> None:
    run_warmup(model_bundle)

    assert len(model_bundle.agent.states) == 1


def test_run_warmup_swallows_failures(
    model_bundle: ModelBundle, caplog: pytest.LogCaptureFixture
) -> None:
    model_bundle.agent.predict = _boom  # type: ignore[method-assign]

    with caplog.at_level(logging.WARNING):
        run_warmup(model_bundle)  # 예외가 밖으로 새면 이 블록에서 실패한다

    assert "워밍업 실패" in caplog.text


def test_startup_runs_warmup(
    model_bundle: ModelBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        lifespan_module, "load_model_bundle", lambda *a, **k: model_bundle
    )

    with TestClient(app):
        assert len(model_bundle.agent.states) == 1


def test_startup_survives_warmup_failure(
    model_bundle: ModelBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    """워밍업이 죽어도 서버는 뜬다 (기동을 막지 않는다)."""
    monkeypatch.setattr(
        lifespan_module, "load_model_bundle", lambda *a, **k: model_bundle
    )
    monkeypatch.setattr(warmup_module, "predict", _boom)

    with TestClient(app) as client:
        response = client.get("/api/v1/nope")

    assert response.status_code == 404

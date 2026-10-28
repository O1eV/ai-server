from __future__ import annotations

import logging
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.core.logging_config import logger
from tests.test_prediction_api import _candles

KEY = "test-not-a-real-key"


@pytest.fixture(autouse=True)
def _reset_warning(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> Iterator[None]:
    monkeypatch.setattr(security, "_warned_unset", False)
    # 앱 로거는 propagate=False라서 caplog 핸들러를 직접 붙인다.
    logger.addHandler(caplog.handler)
    yield
    logger.removeHandler(caplog.handler)


def test_missing_key_header_is_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    response = client.post("/api/v1/predict", json=_candles())

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_wrong_key_is_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    response = client.post("/api/v1/predict", json=_candles(), headers={"X-API-KEY": "wrong"})

    assert response.status_code == 401


def test_correct_key_passes(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    response = client.post("/api/v1/predict", json=_candles(), headers={"X-API-KEY": KEY})

    assert response.status_code == 200
    assert response.json()["decision"] == "BUY"


def test_key_value_is_not_logged_or_returned(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    with caplog.at_level(logging.DEBUG):
        response = client.post("/api/v1/predict", json=_candles(), headers={"X-API-KEY": "guess-1234"})

    assert KEY not in response.text
    assert KEY not in caplog.text
    assert "guess-1234" not in caplog.text


def test_unset_key_allows_requests_with_a_warning(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    with caplog.at_level(logging.WARNING):
        first = client.post("/api/v1/predict", json=_candles())
        second = client.post("/api/v1/predict", json=_candles())

    assert first.status_code == 200
    assert second.status_code == 200
    assert caplog.text.count("MODEL_API_KEY가 설정되지 않아") == 1


def test_only_predict_requires_the_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    # 인증이 걸린 건 예측 라우터뿐이다. 다른 경로는 인증 전에 404가 난다(헬스체크 등 추가해도 키를 요구하지 않는다).
    assert client.get("/api/v1/nope").status_code == 404

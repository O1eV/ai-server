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
def _reset_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> Iterator[None]:
    monkeypatch.setattr(security, "_warned_insecure", False)
    # 앱 로거는 propagate=False라서 caplog 핸들러를 직접 붙인다.
    logger.addHandler(caplog.handler)
    yield
    logger.removeHandler(caplog.handler)


def test_missing_key_header_is_401(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    response = client.post("/api/v1/predict", json=_candles())

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_wrong_key_is_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    response = client.post(
        "/api/v1/predict", json=_candles(), headers={"X-API-KEY": "wrong"}
    )

    assert response.status_code == 401


def test_correct_key_passes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    response = client.post(
        "/api/v1/predict", json=_candles(), headers={"X-API-KEY": KEY}
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "BUY"


def test_key_value_is_not_logged_or_returned(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    with caplog.at_level(logging.DEBUG):
        response = client.post(
            "/api/v1/predict", json=_candles(), headers={"X-API-KEY": "guess-1234"}
        )

    assert KEY not in response.text
    assert KEY not in caplog.text
    assert "guess-1234" not in caplog.text


def test_unset_key_rejects_requests(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("ALLOW_INSECURE_NO_AUTH", raising=False)

    assert client.post("/api/v1/predict", json=_candles()).status_code == 401
    # 키를 보내도 서버에 키가 없으면 통과하지 않는다.
    response = client.post(
        "/api/v1/predict", json=_candles(), headers={"X-API-KEY": "anything"}
    )
    assert response.status_code == 401


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_key_rejects_requests(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, blank: str
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", blank)
    monkeypatch.delenv("ALLOW_INSECURE_NO_AUTH", raising=False)

    assert client.post("/api/v1/predict", json=_candles()).status_code == 401
    response = client.post(
        "/api/v1/predict", json=_candles(), headers={"X-API-KEY": blank}
    )
    assert response.status_code == 401


def test_empty_header_is_401(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    response = client.post(
        "/api/v1/predict", json=_candles(), headers={"X-API-KEY": ""}
    )

    assert response.status_code == 401


def test_explicit_opt_in_allows_requests_with_a_warning(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("ALLOW_INSECURE_NO_AUTH", "1")

    with caplog.at_level(logging.WARNING):
        first = client.post("/api/v1/predict", json=_candles())
        second = client.post("/api/v1/predict", json=_candles())

    assert first.status_code == 200
    assert second.status_code == 200
    assert caplog.text.count("인증 없이 동작합니다") == 1


def test_configured_key_wins_over_insecure_flag(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", KEY)
    monkeypatch.setenv("ALLOW_INSECURE_NO_AUTH", "1")

    assert client.post("/api/v1/predict", json=_candles()).status_code == 401

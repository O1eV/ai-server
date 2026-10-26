from __future__ import annotations

from typing import Any, Dict, List

from fastapi.testclient import TestClient

from app.core.model_loader import ModelBundle
from common.contract import NUM_CANDLES, build_state, candles_from_rows


def _candles(count: int = NUM_CANDLES, start: float = 100.0) -> List[Dict[str, Any]]:
    return [
        {
            "open": start + i - 0.5,
            "high": start + i + 1.0,
            "low": start + i - 1.0,
            "close": start + i,
            "rate": 0.01 * i,
            "volume": 1000 + i,
            "bar_time": f"2026-10-{i + 1:02d}T00:00:00Z",
        }
        for i in range(count)
    ]


def test_predict_returns_decision(client: TestClient) -> None:
    response = client.post("/api/v1/predict", json=_candles())

    assert response.status_code == 200
    assert response.json() == {
        "decision": "BUY",
        "buy": 0.7,
        "sell": 0.1,
        "hold": 0.2,
        "confidence": 0.42,
    }


def test_predict_uses_the_same_state_as_training(
    client: TestClient, model_bundle: ModelBundle, fake_agent: Any
) -> None:
    payload = _candles()
    client.post("/api/v1/predict", json=payload)

    expected = build_state(candles_from_rows(payload[-NUM_CANDLES:]), interval="1d")
    assert fake_agent.states == [expected]


def test_predict_sends_only_the_last_window(client: TestClient, fake_agent: Any) -> None:
    payload = _candles(NUM_CANDLES + 5)
    client.post("/api/v1/predict", json=payload)

    state = fake_agent.states[0]
    header, o_row = state.split("\n")[:2]
    assert header == f"interval=1d n={NUM_CANDLES}"
    assert o_row.split()[1] == f"{(105 - 0.5) / 119.0 * 100 - 100:+.2f}"


def test_too_few_candles_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/predict", json=_candles(NUM_CANDLES - 1))

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_market_data"
    assert str(NUM_CANDLES) in body["detail"]


def test_invalid_candle_is_rejected_by_validation(client: TestClient) -> None:
    payload = _candles()
    payload[-1]["close"] = 0

    response = client.post("/api/v1/predict", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_extra_fields_from_spring_are_ignored(client: TestClient) -> None:
    payload = _candles()
    for candle in payload:
        candle["ticker"] = "005930"

    assert client.post("/api/v1/predict", json=payload).status_code == 200


def test_model_failure_is_reported_as_prediction_failed(
    client: TestClient, model_bundle: ModelBundle
) -> None:
    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("device out of memory")

    model_bundle.agent.predict = boom

    response = client.post("/api/v1/predict", json=_candles())

    assert response.status_code == 500
    assert response.json()["code"] == "prediction_failed"


def test_decision_follows_model_choice_and_ignores_unknown_labels(
    client: TestClient, model_bundle: ModelBundle
) -> None:
    model_bundle.agent.choice = "HOLD"
    model_bundle.agent.probabilities = {
        "BUY": 0.1,
        "SELL": 0.2,
        "HOLD": 0.5,
        "EXTRA": 0.9,
    }

    body = client.post("/api/v1/predict", json=_candles()).json()

    assert body == {
        "decision": "HOLD",
        "buy": 0.1,
        "sell": 0.2,
        "hold": 0.5,
        "confidence": 0.42,
    }

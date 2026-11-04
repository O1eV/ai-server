from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.core.model_loader import ModelBundle
from app.dto.request.stock_data import StockData
from app.services.prediction import predict
from tests.test_prediction_api import _candles


@pytest.mark.parametrize(
    ("model_path", "expected"),
    [
        ("tests/fake-checkpoint", "fake-checkpoint"),
        ("/models/laya-v3/", "laya-v3"),
        ("org/laya-hub-model", "laya-hub-model"),
        ("", None),
    ],
)
def test_model_version_comes_from_the_loaded_path(
    model_bundle: ModelBundle, model_path: str, expected: str | None
) -> None:
    assert replace(model_bundle, model_path=model_path).model_version == expected


def test_predict_response_carries_model_version(client: TestClient) -> None:
    body = client.post("/api/v1/predict", json=_candles()).json()

    assert body["model_version"] == "fake-checkpoint"


def test_predict_response_model_version_is_null_when_unknown(
    model_bundle: ModelBundle,
) -> None:
    candles = [StockData(**row) for row in _candles()]

    decision = predict(candles, replace(model_bundle, model_path=""))

    assert decision.model_dump()["model_version"] is None

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.exceptions import PredictionError
from app.core.model_loader import ModelBundle
from app.dto.request.stock_data import StockData
from app.services.prediction import predict
from common.contract import NUM_CANDLES, QUESTIONS
from tests.conftest import FakeAgent


class ConcurrencyProbeAgent(FakeAgent):
    """동시에 실행 중인 predict 호출 수의 최댓값을 기록하는 가짜 모델."""

    def __init__(self) -> None:
        super().__init__()
        self._guard = threading.Lock()
        self.running = 0
        self.max_running = 0

    def predict(self, state: str, questions: dict) -> dict:
        with self._guard:
            self.running += 1
            self.max_running = max(self.max_running, self.running)
        time.sleep(0.05)
        try:
            return super().predict(state, questions)
        finally:
            with self._guard:
                self.running -= 1


def _candles() -> list[StockData]:
    return [
        StockData(
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.5 + i,
            volume=1000.0,
            bar_time=f"2026-10-01T00:{i:02d}:00Z",
        )
        for i in range(NUM_CANDLES)
    ]


def test_inference_is_serialized_across_threads(model_bundle: ModelBundle) -> None:
    agent = ConcurrencyProbeAgent()
    bundle = ModelBundle(
        agent=agent,
        device="cpu",
        model_path=model_bundle.model_path,
        questions=QUESTIONS,
        loaded_at=model_bundle.loaded_at,
    )

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: predict(_candles(), bundle), range(6)))

    assert len(results) == 6
    assert len(agent.states) == 6
    assert agent.max_running == 1


def test_failed_inference_releases_the_lock(model_bundle: ModelBundle) -> None:
    class FailingOnce(FakeAgent):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def predict(self, state: str, questions: dict) -> dict:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("boom")
            return super().predict(state, questions)

    agent = FailingOnce()
    bundle = ModelBundle(
        agent=agent,
        device="cpu",
        model_path=model_bundle.model_path,
        questions=QUESTIONS,
        loaded_at=model_bundle.loaded_at,
    )

    with pytest.raises(PredictionError):
        predict(_candles(), bundle)

    assert predict(_candles(), bundle).decision == "BUY"

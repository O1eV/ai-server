from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional

import pytest
from fastapi.testclient import TestClient

from app.core import lifespan as lifespan_module
from app.core.model_loader import ModelBundle
from app.main import app
from common.contract import QUESTIONS


class FakeAgent:
    def __init__(
        self,
        choice: str = "BUY",
        probabilities: Optional[Dict[str, float]] = None,
    ) -> None:
        self.choice = choice
        self.probabilities = probabilities or {"BUY": 0.7, "SELL": 0.1, "HOLD": 0.2}
        self.states: List[str] = []

    def predict(self, state: str, questions: Dict) -> Dict:
        self.states.append(state)
        return {
            "answers": {
                "action": {
                    "type": "choice",
                    "choice": self.choice,
                    "probabilities": dict(self.probabilities),
                    "confidence": 0.42,
                    "answer_confidence": 0.42,
                    "action": {"act_probability": 1.0},
                }
            },
            "usage": {},
        }


@pytest.fixture
def fake_agent() -> FakeAgent:
    return FakeAgent()


@pytest.fixture
def model_bundle(fake_agent: FakeAgent) -> ModelBundle:
    return ModelBundle(
        agent=fake_agent,
        device="cpu",
        model_path="tests/fake-checkpoint",
        questions=QUESTIONS,
        loaded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def client(model_bundle: ModelBundle, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(lifespan_module, "load_model_bundle", lambda *a, **k: model_bundle)
    with TestClient(app) as test_client:
        yield test_client

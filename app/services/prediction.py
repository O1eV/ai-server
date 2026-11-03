from __future__ import annotations

import threading
from typing import Any, Dict, Mapping, Sequence

from app.core.config import get_settings
from app.core.exceptions import InvalidMarketDataError, PredictionError
from app.core.logging_config import logger
from app.core.model_loader import ModelBundle
from app.dto.request.stock_data import StockData
from app.dto.response.stock_decision import Decision
from common.contract import LABELS, NUM_CANDLES, QUESTION_ID, build_state, candles_from_rows

# MPS(Metal) 모델을 여러 스레드가 동시에 호출하면 프로세스가 죽는다(MTLCommandBuffer assertion).
# 동기 엔드포인트는 스레드풀에서 동시에 실행되므로 추론 구간만 프로세스 전역 락으로 직렬화한다.
_INFERENCE_LOCK = threading.Lock()


def _probabilities(answer: Mapping[str, Any]) -> Dict[str, float]:
    raw = answer.get("probabilities") or {}
    if not isinstance(raw, Mapping):
        raise PredictionError("모델 응답의 probabilities 형식이 올바르지 않습니다.")
    return {label: float(raw.get(label, 0.0)) for label in LABELS}


def predict(candles: Sequence[StockData], bundle: ModelBundle) -> Decision:
    if len(candles) < NUM_CANDLES:
        raise InvalidMarketDataError(
            f"봉은 최소 {NUM_CANDLES}개가 필요합니다 (받은 개수: {len(candles)})"
        )

    recent = candles[-NUM_CANDLES:]
    state = build_state(
        candles_from_rows([candle.model_dump() for candle in recent]),
        interval=get_settings().interval,
    )

    try:
        with _INFERENCE_LOCK:
            result = bundle.agent.predict(state, bundle.questions)
    except Exception as exc:
        logger.exception("모델 추론 실패")
        raise PredictionError("모델 추론에 실패했습니다.") from exc

    answer = (result.get("answers") or {}).get(QUESTION_ID)
    if not isinstance(answer, Mapping) or "choice" not in answer:
        logger.error("모델 응답에 action 답변이 없습니다: %s", str(result)[:500])
        raise PredictionError("모델 응답 형식이 올바르지 않습니다.")

    probabilities = _probabilities(answer)
    confidence = answer.get("answer_confidence", answer.get("confidence"))
    if confidence is None:
        confidence = max(probabilities.values())

    return Decision(
        decision=str(answer["choice"]),
        buy=probabilities["BUY"],
        sell=probabilities["SELL"],
        hold=probabilities["HOLD"],
        confidence=float(confidence),
    )

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.logging_config import logger
from app.core.model_loader import ModelBundle
from app.dto.request.stock_data import StockData
from app.services.prediction import predict
from common.contract import NUM_CANDLES

WARMUP_BASE_PRICE = 100.0
WARMUP_FIRST_DAY = datetime(2026, 1, 1, tzinfo=UTC)


def build_warmup_candles(count: int = NUM_CANDLES) -> list[StockData]:
    """워밍업용 더미 캔들.

    추론 경로가 정상이려면 봉이 최소 NUM_CANDLES개이고 close > 0 이어야 한다.
    bar_time은 오름차순이어야 state 빌드가 실제 데이터와 같은 순서로 동작한다.
    """
    candles: list[StockData] = []
    for i in range(count):
        close = WARMUP_BASE_PRICE + i
        candles.append(
            StockData(
                open=close - 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                rate=0.5,
                volume=1000.0 + i,
                bar_time=WARMUP_FIRST_DAY.replace(day=1 + (i % 27)).isoformat(),
            )
        )
    return candles


def run_warmup(bundle: ModelBundle) -> None:
    """서버 시작 시 predict를 1회 호출해 첫 요청 지연을 없앤다.

    첫 추론이 약 3초 걸려 Spring의 500ms 타임아웃을 넘는 문제를 막기 위한 것이다.
    워밍업 실패는 서버 기동을 막지 않는다. 로그만 남기고 계속 진행한다.
    """
    settings = get_settings()
    try:
        decision = predict(build_warmup_candles(), bundle)
    except Exception:  # noqa: BLE001 - 워밍업 실패는 기동을 막지 않는다 (이슈 요구)
        logger.warning("워밍업 실패(무시하고 계속 시작)", exc_info=True)
        return
    logger.info("워밍업 완료: %s (interval=%s)", decision.decision, settings.interval)

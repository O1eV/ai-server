from __future__ import annotations

from pydantic import BaseModel, Field


class StockData(BaseModel):
    open: float
    high: float
    low: float
    close: float = Field(gt=0, description="최근 종가 기준 상대값 계산에 쓰이므로 0보다 커야 한다")
    rate: float | None = Field(default=None, description="등락률 (추론에는 쓰지 않음)")
    volume: float = Field(default=0.0, ge=0)
    bar_time: str = Field(description="봉 시각 (ISO8601 등)")

    model_config = {"extra": "ignore"}

from __future__ import annotations

from pydantic import BaseModel, Field


class Decision(BaseModel):
    decision: str = Field(description="BUY / SELL / HOLD")
    buy: float
    sell: float
    hold: float
    confidence: float
    model_version: str | None = Field(
        default=None, description="로드한 가중치 경로의 이름 (알 수 없으면 null)"
    )

from __future__ import annotations

from pydantic import BaseModel, Field


class Decision(BaseModel):
    decision: str = Field(description="BUY / SELL / HOLD")
    buy: float
    sell: float
    hold: float
    confidence: float

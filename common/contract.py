from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Sequence

QUESTION_ID = "action"
NUM_CANDLES = 15
DEFAULT_INTERVAL = "1d"
LABELS = ("BUY", "SELL", "HOLD")
DECIMALS = 2

QUESTIONS: Dict[str, Dict[str, Any]] = {
    QUESTION_ID: {
        "type": "choice",
        "instructions": (
            "The state shows the last 15 candles of one instrument, oldest first. "
            "o/h/l/c are percent changes from the latest close, and v is volume relative to "
            "the 15-candle average volume (1.00 = average). "
            "Decide the action to take from now: BUY if price is likely to rise meaningfully, "
            "SELL if it is likely to fall meaningfully, HOLD if the direction is unclear or the "
            "expected move is too small to be worth acting on."
        ),
        "criteria": {
            "BUY": (
                "Meaningful rise expected: strong upward momentum, price holding above recent "
                "lows, wider up-candles with rising volume, or a breakout from a range"
            ),
            "SELL": (
                "Meaningful fall expected: weakening momentum, price below recent lows, long "
                "down-candles with rising volume, or a break down out of a range"
            ),
            "HOLD": (
                "No clear direction: range-bound or choppy candles, low volume, mixed signals, "
                "or an expected move too small to justify the cost"
            ),
        },
    }
}


def _pct(value: float) -> str:
    return f"{value * 100.0:+.{DECIMALS}f}"


def build_state(
    candles: Sequence[Mapping[str, Any]], interval: str = DEFAULT_INTERVAL
) -> str:
    if len(candles) < NUM_CANDLES:
        raise ValueError(
            f"state에는 최소 {NUM_CANDLES}개의 캔들이 필요합니다 (받은 개수: {len(candles)})"
        )
    window = list(candles[-NUM_CANDLES:])

    try:
        closes = [float(c["close"]) for c in window]
        opens = [float(c["open"]) for c in window]
        highs = [float(c["high"]) for c in window]
        lows = [float(c["low"]) for c in window]
        volumes = [float(c["volume"] or 0) for c in window]
    except (KeyError, TypeError) as exc:
        raise ValueError("각 캔들은 open/high/low/close/volume 키를 가져야 합니다") from exc

    base = closes[-1]
    if not base or base <= 0 or not math.isfinite(base):
        raise ValueError(f"최근 종가가 올바르지 않습니다: {window[-1].get('close')!r}")

    mean_volume = sum(volumes) / len(volumes)

    rows = {
        "o": [_pct(value / base - 1.0) for value in opens],
        "h": [_pct(value / base - 1.0) for value in highs],
        "l": [_pct(value / base - 1.0) for value in lows],
        "c": [_pct(value / base - 1.0) for value in closes],
        "v": ["1.00"] * NUM_CANDLES
        if mean_volume <= 0
        else [f"{value / mean_volume:.2f}" for value in volumes],
    }

    lines = [f"interval={interval} n={NUM_CANDLES}"]
    for name in ("o", "h", "l", "c", "v"):
        lines.append(f"{name} " + " ".join(rows[name]))

    if len(closes) > 1:
        lines.append(
            "ret "
            + " ".join(
                f"{n}:{_pct(closes[-1] / closes[-1 - n] - 1.0)}"
                for n in (1, 2, 3, 5)
                if len(closes) > n
            )
        )

    return "\n".join(lines)


def candles_from_rows(rows: Iterable[Mapping[str, Any]]) -> List[Dict[str, float]]:
    return [
        {
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row.get("volume") or 0),
        }
        for row in rows
    ]


def warmup_state(interval: str = DEFAULT_INTERVAL) -> str:
    candles = [
        {"open": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i, "close": 100.5 + i, "volume": 1000.0 + i}
        for i in range(NUM_CANDLES)
    ]
    return build_state(candles, interval=interval)

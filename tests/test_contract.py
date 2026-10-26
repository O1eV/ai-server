from __future__ import annotations

import pytest

from common.contract import (
    LABELS,
    NUM_CANDLES,
    QUESTION_ID,
    QUESTIONS,
    build_state,
    candles_from_rows,
    warmup_state,
)


def _flat_candles(n: int = NUM_CANDLES) -> list[dict[str, float]]:
    return [
        {"open": 99.0, "high": 101.0, "low": 98.0, "close": 100.0, "volume": 1000.0}
        for _ in range(n)
    ]


def test_build_state_layout_is_stable() -> None:
    state = build_state(_flat_candles(), interval="1d")
    lines = state.split("\n")

    assert lines[0] == f"interval=1d n={NUM_CANDLES}"
    assert lines[1] == "o " + " ".join(["-1.00"] * NUM_CANDLES)
    assert lines[2] == "h " + " ".join(["+1.00"] * NUM_CANDLES)
    assert lines[3] == "l " + " ".join(["-2.00"] * NUM_CANDLES)
    assert lines[4] == "c " + " ".join(["+0.00"] * NUM_CANDLES)
    assert lines[5] == "v " + " ".join(["1.00"] * NUM_CANDLES)
    assert lines[6] == "ret 1:+0.00 2:+0.00 3:+0.00 5:+0.00"
    assert len(lines) == 7


def test_build_state_uses_the_last_window_only() -> None:
    extra = [
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 10.0}
        for _ in range(5)
    ]
    assert build_state(extra + _flat_candles()) == build_state(_flat_candles())


def test_build_state_relative_rows_use_latest_close() -> None:
    candles = _flat_candles()
    candles[-1]["close"] = 200.0
    lines = build_state(candles).split("\n")
    assert lines[4].split()[1:] == ["-50.00"] * (NUM_CANDLES - 1) + ["+0.00"]


def test_build_state_rejects_short_or_broken_input() -> None:
    with pytest.raises(ValueError):
        build_state(_flat_candles(NUM_CANDLES - 1))

    zero = _flat_candles()
    zero[-1]["close"] = 0.0
    with pytest.raises(ValueError):
        build_state(zero)

    with pytest.raises(ValueError):
        build_state([{"open": 1.0} for _ in range(NUM_CANDLES)])


def test_question_schema_matches_labels() -> None:
    question = QUESTIONS[QUESTION_ID]
    assert question["type"] == "choice"
    assert tuple(question["criteria"]) == LABELS


def test_candles_from_rows_accepts_missing_volume() -> None:
    rows = [{"open": 1, "high": 2, "low": 0.5, "close": 1.5}]
    assert candles_from_rows(rows) == [
        {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 0.0}
    ]


def test_warmup_state_is_a_valid_state() -> None:
    lines = warmup_state().split("\n")
    assert lines[0] == f"interval=1d n={NUM_CANDLES}"
    assert len(lines) == 7

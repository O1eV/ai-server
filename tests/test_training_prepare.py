from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from common.contract import NUM_CANDLES
from training.train import build_symbol_windows, label_of, load_series, pick_threshold


def _raw_frame(rows: int = 40) -> pd.DataFrame:
    close = 100.0 + np.arange(rows, dtype="float64")
    return pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=rows, freq="D"),
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.full(rows, 1_000.0),
        }
    )


def _normalised_frame(rows: int = 40) -> pd.DataFrame:
    frame = _raw_frame(rows)
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(frame["Date"], utc=True),
            "open": frame["Open"].to_numpy(dtype="float64"),
            "high": frame["High"].to_numpy(dtype="float64"),
            "low": frame["Low"].to_numpy(dtype="float64"),
            "close": frame["Close"].to_numpy(dtype="float64"),
            "volume": frame["Volume"].to_numpy(dtype="float64"),
        }
    )


def test_load_series_normalises_column_aliases(tmp_path: Path) -> None:
    path = tmp_path / "AAPL.csv"
    _raw_frame().to_csv(path, index=False)

    data = load_series(path, "AAPL")

    assert list(data.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(data) == 40
    assert data["close"].is_monotonic_increasing


def test_load_series_sorts_and_drops_duplicate_timestamps(tmp_path: Path) -> None:
    frame = pd.concat([_raw_frame(), _raw_frame().tail(1)], ignore_index=True)
    path = tmp_path / "dup.csv"
    frame.iloc[::-1].to_csv(path, index=False)

    data = load_series(path, "dup")

    assert len(data) == 40
    assert data["timestamp"].is_monotonic_increasing


def test_load_series_rejects_frames_without_ohlc(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    pd.DataFrame(
        {"Date": pd.date_range("2024-01-01", periods=30), "foo": range(30)}
    ).to_csv(path, index=False)

    with pytest.raises(ValueError):
        load_series(path, "bad")


def test_build_symbol_windows_counts_and_forward_returns() -> None:
    data = _normalised_frame()

    built = build_symbol_windows(data, "X", horizon=5)

    expected = len(data) - NUM_CANDLES - 5 + 1
    assert built is not None
    assert len(built["starts"]) == expected
    assert built["starts"][0] == 0
    assert built["starts"][-1] == expected - 1

    close = data["close"].to_numpy()
    assert built["forward"][0] == pytest.approx(
        close[NUM_CANDLES - 1 + 5] / close[NUM_CANDLES - 1] - 1.0
    )


def test_build_symbol_windows_returns_none_when_too_short() -> None:
    data = _normalised_frame(NUM_CANDLES + 4)

    assert build_symbol_windows(data, "X", horizon=5) is None


def test_label_of_uses_inclusive_thresholds() -> None:
    assert label_of(0.05, 0.02) == "BUY"
    assert label_of(0.02, 0.02) == "BUY"
    assert label_of(-0.02, 0.02) == "SELL"
    assert label_of(0.019, 0.02) == "HOLD"


def test_pick_threshold_balances_classes() -> None:
    rng = np.random.default_rng(0)
    returns = rng.normal(0.0, 0.02, size=4000)

    threshold = pick_threshold(returns, target_buy=0.3, target_sell=0.3)

    assert threshold > 0
    assert 0.25 < float((returns >= threshold).mean()) < 0.35
    assert 0.25 < float((returns <= -threshold).mean()) < 0.35

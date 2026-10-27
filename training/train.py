from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from common.contract import (
    DECIMALS,
    DEFAULT_INTERVAL,
    LABELS,
    NUM_CANDLES,
    QUESTIONS,
    build_state,
)

DEFAULT_DATA = "bguzzo2k/ohlc_1d_mixture"
DEFAULT_OUT = "data/laya-trading"
DEFAULT_OUTPUT = "outputs/laya-trading"
DEFAULT_MODEL = "models/Laya"

DEFAULT_SYMBOLS = [
    "^KS11", "^N225", "^DJI", "^GSPC", "^IXIC", "^RUT", "^FTSE", "^GDAXI", "^FCHI",
    "^IBEX", "^STOXX50E", "^HSI", "^TWII", "^NSEI", "^BSESN", "^BVSP", "^MXX",
    "^GSPTSE", "^AXJO", "^AORD", "^NZ50", "^JKSE", "^KLSE", "^OMXC20",
    "EURUSD=X", "GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "JPY=X", "KRW=X", "CNY=X",
    "HKD=X", "CHF=X", "CAD=X", "MXN=X", "BRL=X", "EURJPY=X", "GBPJPY=X", "EURGBP=X",
    "ES=F", "NQ=F", "YM=F", "RTY=F", "GC=F", "SI=F", "HG=F", "CL=F", "NG=F",
    "ZC=F", "ZW=F", "ZS=F", "ZB=F", "ZN=F", "6E=F", "6B=F", "6J=F", "6A=F",
    "6C=F", "6S=F",
    "BTC-USD", "ETH-USD", "XRP-USD", "SOL-USD", "ADA-USD", "DOGE-USD", "DOT-USD",
    "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD", "XLM-USD", "ATOM-USD", "NEAR-USD",
    "APT-USD", "MATIC-USD", "SHIB-USD", "AAVE-USD", "UNI-USD", "FIL-USD",
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "JPM", "V", "MA",
    "UNH", "JNJ", "PG", "KO", "PEP", "XOM", "CVX", "WMT", "DIS", "NFLX",
    "AMD", "INTC", "CSCO", "CRM", "ORCL", "ADBE", "QCOM", "TXN", "BA", "CAT",
    "GE", "F", "GM", "UBER", "ABNB", "PYPL", "COIN", "DAL", "COST", "HD",
    "MCD", "SBUX", "NKE", "IBM", "INTU", "PLTR", "GS", "AXP", "BAC", "WFC",
    "T", "VZ", "BRK-B",
    "AGG", "GLD", "TLT",
]

HF_PATTERNS = (
    "{interval}/{symbol}_max_{interval}.parquet",
    "{interval}/{symbol}.parquet",
    "{symbol}.parquet",
    "{interval}/{symbol}_max_1d.parquet",
)


def resolve_series_files(data: str, symbols, interval: str):
    path = Path(data)

    if path.exists():
        if path.is_dir():
            files = sorted(
                list(path.glob("*.parquet"))
                + list(path.glob("*.csv"))
                + list(path.glob("*.jsonl"))
            )
            if not files:
                raise FileNotFoundError(f"{path} 아래에 parquet/csv/jsonl 파일이 없습니다.")
            return [(f.stem, f) for f in files]
        return [(path.stem, path)]

    from huggingface_hub import hf_hub_download

    found, missing = [], []
    for symbol in symbols:
        saved = None
        for pattern in HF_PATTERNS:
            filename = pattern.format(interval=interval, symbol=symbol)
            try:
                saved = hf_hub_download(
                    repo_id=data, filename=filename, repo_type="dataset"
                )
                break
            except Exception:
                continue
        if saved is None:
            missing.append(symbol)
        else:
            found.append((symbol, Path(saved)))

    if not found:
        raise FileNotFoundError(
            f"HuggingFace 저장소 {data!r}에서 종목 파일을 찾지 못했습니다. "
            f"--symbols를 확인하세요. (예: {symbols[:5]})"
        )
    print(f"HuggingFace 저장소 {data}에서 종목 {len(found)}개를 받았습니다.")
    if missing:
        print(f"  저장소에 없어 건너뛴 종목 {len(missing)}개: {', '.join(missing[:20])}"
              + (" ..." if len(missing) > 20 else ""))
    return found


_TIMESTAMP_ALIASES = ("timestamp", "datetime", "date", "time", "ts", "candle_date_time_utc")
_OPEN_ALIASES = ("open", "opening_price", "o")
_HIGH_ALIASES = ("high", "high_price", "h")
_LOW_ALIASES = ("low", "low_price", "l")
_CLOSE_ALIASES = ("close", "closing_price", "trade_price", "c", "adj close", "adjusted_close")
_VOLUME_ALIASES = ("volume", "acc_trade_volume", "candle_acc_trade_volume", "v")


def _find_column(columns, aliases):
    lookup = {}
    for col in columns:
        if isinstance(col, tuple):
            col = col[-1]
        lookup[str(col).strip().lower()] = col
    for alias in aliases:
        if alias in lookup:
            return lookup[alias]
    return None


def load_series(path: Path, symbol: str):
    import pandas as pd

    suffix = path.suffix.lower()
    if suffix == ".parquet":
        frame = pd.read_parquet(path)
    elif suffix == ".csv":
        frame = pd.read_csv(path)
    else:
        frame = pd.read_json(path, lines=True)

    if not isinstance(frame, pd.DataFrame):
        raise ValueError(f"{path}: 표 형태가 아닙니다 ({type(frame).__name__})")

    timestamp_col = _find_column(frame.columns, _TIMESTAMP_ALIASES)
    if timestamp_col is None and not isinstance(frame.index, pd.RangeIndex):
        timestamp_col = frame.index.name or "timestamp"
        frame = frame.reset_index()

    column_map = {
        "timestamp": timestamp_col,
        "open": _find_column(frame.columns, _OPEN_ALIASES),
        "high": _find_column(frame.columns, _HIGH_ALIASES),
        "low": _find_column(frame.columns, _LOW_ALIASES),
        "close": _find_column(frame.columns, _CLOSE_ALIASES),
        "volume": _find_column(frame.columns, _VOLUME_ALIASES),
    }

    if any(column_map[key] is None for key in ("open", "high", "low", "close")):
        raise ValueError(
            f"{path} ({symbol}): OHLC 컬럼을 찾지 못했습니다. "
            f"찾은 컬럼: {list(frame.columns)}"
        )

    data = pd.DataFrame({"timestamp": frame[column_map["timestamp"]]})
    for key in ("open", "high", "low", "close", "volume"):
        source = column_map[key]
        if source is None:
            data[key] = 0.0
        else:
            data[key] = pd.to_numeric(frame[source], errors="coerce")

    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="coerce")
    data = data.dropna(subset=["timestamp", "open", "high", "low", "close"])
    data = data[data["close"] > 0]
    data = data.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    if len(data) < NUM_CANDLES + 2:
        raise ValueError(f"{path} ({symbol}): 봉이 너무 적습니다 ({len(data)}개).")
    return data


def build_symbol_windows(data, symbol: str, horizon: int):
    import numpy as np

    close = data["close"].to_numpy(dtype="float64")
    stamps = data["timestamp"].to_numpy(dtype="datetime64[ns]").astype("int64")
    n = len(close)
    last_start = n - NUM_CANDLES - horizon
    if last_start < 0:
        return None

    starts = np.arange(0, last_start + 1, dtype="int64")
    end_index = starts + NUM_CANDLES - 1
    future_index = end_index + horizon
    forward = close[future_index] / close[end_index] - 1.0
    return {
        "symbol": symbol,
        "starts": starts,
        "forward": forward,
        "timestamps": stamps[end_index],
    }


def _evenly_spaced(indices, limit):
    if limit <= 0 or len(indices) <= limit:
        return list(indices)
    step = len(indices) / float(limit)
    picked = sorted({int(i * step) for i in range(limit)})
    return [indices[i] for i in picked]


def pick_threshold(forward_returns, target_buy: float, target_sell: float) -> float:
    import numpy as np

    values = np.abs(np.asarray(forward_returns, dtype="float64"))
    values = values[np.isfinite(values) & (values > 0)]
    if values.size == 0:
        raise ValueError("미래 수익률을 계산할 값이 없습니다.")

    returns = np.asarray(forward_returns, dtype="float64")
    grid = np.quantile(values, np.linspace(0.20, 0.80, 61))
    best_threshold, best_score = float(grid[len(grid) // 2]), float("inf")
    for threshold in grid:
        buy = float((returns >= threshold).mean())
        sell = float((returns <= -threshold).mean())
        score = abs(buy - target_buy) + abs(sell - target_sell)
        if score < best_score:
            best_threshold, best_score = float(threshold), score
    return best_threshold


def label_of(forward_return: float, threshold: float) -> str:
    if forward_return >= threshold:
        return "BUY"
    if forward_return <= -threshold:
        return "SELL"
    return "HOLD"


def prepare_dataset(args):
    import numpy as np

    symbols = [s.strip() for s in (args.symbols or "").replace(",", " ").split() if s.strip()]
    sources = [s.strip() for s in args.data.split(",") if s.strip()]
    if len(sources) > 1:
        raise ValueError("현재는 --data 하나만 지원합니다 (여러 시장 조합이 필요하면 나중에 확장).")

    series_files = resolve_series_files(sources[0], symbols, args.interval)

    per_symbol, used_symbols, skipped = {}, [], []
    total_windows = 0
    for symbol, file_path in series_files:
        try:
            frame = load_series(file_path, symbol)
        except ValueError as exc:
            skipped.append(f"{symbol}: {exc}")
            continue
        built = build_symbol_windows(frame, symbol, args.horizon)
        if built is None:
            skipped.append(f"{symbol}: 봉 수 부족")
            continue
        _WINDOW_CACHE[symbol] = frame
        _SYMBOL_STARTS[symbol] = built["starts"]
        per_symbol[symbol] = built
        used_symbols.append(symbol)
        total_windows += len(built["starts"])

    if not per_symbol:
        raise ValueError("학습에 쓸 수 있는 윈도우가 하나도 없습니다.\n" + "\n".join(skipped[:10]))

    print(f"사용 종목: {len(used_symbols)}개 / 전체 윈도우: {total_windows:,}개")

    all_stamps = np.concatenate([b["timestamps"] for b in per_symbol.values()])
    cutoff = float(np.quantile(all_stamps.astype("float64"), 1.0 - args.eval_ratio))
    cutoff_text = datetime.fromtimestamp(cutoff / 1e9, tz=timezone.utc).isoformat()

    train_fwds = np.concatenate([
        b["forward"][b["timestamps"] <= cutoff] for b in per_symbol.values()
    ])

    if args.threshold is not None:
        threshold = float(args.threshold)
        threshold_mode = "manual"
    else:
        threshold = pick_threshold(train_fwds, args.target_buy, args.target_sell)
        threshold_mode = "auto"

    train_rows, eval_rows = [], []
    class_counter = {"train": {k: 0 for k in LABELS}, "eval": {k: 0 for k in LABELS}}
    for symbol in used_symbols:
        built = per_symbol[symbol]
        is_train = built["timestamps"] <= cutoff
        train_idx = np.flatnonzero(is_train).tolist()
        eval_idx = np.flatnonzero(~is_train).tolist()

        for split, indices, limit in (
            ("train", train_idx, args.max_per_symbol),
            ("eval", eval_idx, args.max_eval_per_symbol),
        ):
            for i in _evenly_spaced(indices, limit):
                label = label_of(float(built["forward"][i]), threshold)
                row = {
                    "state": build_state(load_window_frame(symbol, i), interval=args.interval),
                    "questions": QUESTIONS,
                    "expected": {"action": label},
                }
                class_counter[split][label] += 1
                (train_rows if split == "train" else eval_rows).append(row)

    if args.limit:
        train_rows = train_rows[: args.limit]
        eval_rows = eval_rows[: max(1, int(args.limit * args.eval_ratio))]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    train_path = out_dir / "train.jsonl"
    eval_path = out_dir / "eval.jsonl"

    def _write(path, rows):
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    _write(train_path, train_rows)
    _write(eval_path, eval_rows)

    meta = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_source": sources[0],
        "interval": args.interval,
        "num_candles": NUM_CANDLES,
        "horizon": args.horizon,
        "threshold": threshold,
        "threshold_mode": threshold_mode,
        "target_buy": args.target_buy,
        "target_sell": args.target_sell,
        "eval_ratio": args.eval_ratio,
        "eval_cutoff": cutoff_text,
        "max_per_symbol": args.max_per_symbol,
        "max_eval_per_symbol": args.max_eval_per_symbol,
        "symbols_used": used_symbols,
        "symbols_skipped": skipped,
        "counts": {
            "train": len(train_rows),
            "eval": len(eval_rows),
            "class_train": class_counter["train"],
            "class_eval": class_counter["eval"],
        },
        "decimals": DECIMALS,
        "note": (
            "state의 o/h/l/c는 최근 종가 대비 %, v는 15봉 평균 거래량 대비 배율이다. "
            "추론 시에는 common.contract.build_state()를 그대로 사용할 것."
        ),
    }
    with (out_dir / "meta.json").open("w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)

    print(f"\n라벨 기준: 미래 {args.horizon}봉 수익률 {threshold * 100:+.2f}% ({threshold_mode})")
    print(f"train={len(train_rows):,}  eval={len(eval_rows):,}  (eval cutoff: {cutoff_text[:10]})")
    for split in ("train", "eval"):
        counts = class_counter[split]
        size = max(1, sum(counts.values()))
        print(f"  {split:<5} " + "  ".join(
            f"{label}={counts[label]:,} ({counts[label] / size * 100:4.1f}%)"
            for label in LABELS
        ))
    if skipped:
        print(f"건너뛴 종목: {len(skipped)}개 (예: {skipped[0]})")

    print("\n--- state 예시 (추론 시 build_state()가 만드는 것과 동일해야 함) ---")
    print(train_rows[0]["state"])
    print("---------------------------------------------------------------------\n")

    return train_path, eval_path, meta


def load_window_frame(symbol: str, index: int):
    frame = _WINDOW_CACHE[symbol]
    start = int(_SYMBOL_STARTS[symbol][index])
    window = frame.iloc[start: start + NUM_CANDLES]
    return [
        {
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
        }
        for row in window.itertuples(index=False)
    ]


_WINDOW_CACHE = {}
_SYMBOL_STARTS = {}


def run_training(args, train_path: Path, eval_path: Path):
    from laya.train import TrainConfig, dry_run, finetune

    config = TrainConfig(
        epochs=args.epochs,
        micro_batch=args.micro_batch,
        grad_accum=args.grad_accum,
        loss=args.loss,
        shuffle_options=("choice",),
        freeze_encoder=args.freeze_encoder,
        max_len=args.max_len,
        head_max_len=args.head_max_len,
        eval_data=str(eval_path),
        seed=args.seed,
        amp=True if args.amp else None,
        gradient_checkpointing=True if args.gradient_checkpointing else None,
    )
    config.validate()

    print(f"모델: {args.model}")
    print("가중치를 로딩하기 전 데이터 통계(dry-run)...")
    summary = dry_run(str(train_path), args.model, config)
    if args.dry_run:
        print("\n--dry-run: 데이터 준비 상태만 확인하고 학습은 실행하지 않았습니다.")
        return summary

    result = finetune(str(train_path), args.model, str(args.output), config, device=args.device)

    print("\n학습 완료.")
    print(f"  체크포인트: {result['output_dir']}   (laya.load()로 바로 로드 가능)")
    print(f"  질문 스키마: {Path(result['output_dir']) / 'questions.json'}")
    print(f"  학습 리포트: {Path(result['output_dir']) / 'train_report.json'}")
    print(
        "\n추론 예시:\n"
        "  import laya\n"
        f"  agent = laya.load({str(args.output)!r})\n"
        "  from common.contract import build_state, QUESTIONS\n"
        "  state = build_state(candles, interval=...)\n"
        "  answer = agent.predict(state, QUESTIONS)['answers']['action']\n"
        "  print(answer['choice'], answer['probabilities'])"
    )
    return result


def add_data_args(parser):
    parser.add_argument("--data", default=DEFAULT_DATA,
                        help="HuggingFace 데이터셋 id 또는 로컬 parquet/csv/jsonl 경로")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS),
                        help="사용할 종목 목록 (쉼표/공백 구분). 빈 문자열이면 저장소 전체 사용")
    parser.add_argument("--interval", default=DEFAULT_INTERVAL,
                        help="캔들 주기 표기 (state 첫 줄에 기록됨. 서버에서도 같은 값이어야 함)")
    parser.add_argument("--horizon", type=int, default=5,
                        help="미래 몇 봉의 수익률로 라벨을 만들지 (기본 5)")
    parser.add_argument("--threshold", type=float, default=None,
                        help="BUY/SELL 판단 기준 수익률(소수). 지정하지 않으면 클래스 균형으로 자동 추정")
    parser.add_argument("--target-buy", type=float, default=0.30, help="자동 threshold의 BUY 목표 비중")
    parser.add_argument("--target-sell", type=float, default=0.30, help="자동 threshold의 SELL 목표 비중")
    parser.add_argument("--eval-ratio", type=float, default=0.10, help="마지막 구간 중 평가에 쓸 비중")
    parser.add_argument("--max-per-symbol", type=int, default=400, help="종목당 최대 train 윈도우 수")
    parser.add_argument("--max-eval-per-symbol", type=int, default=60, help="종목당 최대 eval 윈도우 수")
    parser.add_argument("--limit", type=int, default=0, help="전체 윈도우 수 제한 (스모크 테스트용)")
    parser.add_argument("--out", default=DEFAULT_OUT, help="준비된 JSONL을 저장할 폴더")


def add_train_args(parser):
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Laya 체크포인트 경로")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="파인튜닝 결과 저장 폴더")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--micro-batch", type=int, default=1,
                        help="한 번에 묶을 샘플 수. 16GB 맥에서는 1을 권장 (2는 --gradient-checkpointing 동반)")
    parser.add_argument("--grad-accum", type=int, default=64,
                        help="그래디언트 누적 횟수. effective batch = micro-batch × grad-accum")
    parser.add_argument("--loss", choices=["rlcd", "soft-ce"], default="rlcd")
    parser.add_argument("--max-len", type=int, default=None, help="state 최대 토큰 (기본: 체크포인트 설정)")
    parser.add_argument("--head-max-len", type=int, default=None, help="질문/선택지 최대 토큰")
    parser.add_argument("--amp", action="store_true",
                        help="혼합정밀(fp16 autocast) 사용. 활성화 메모리를 크게 줄인다")
    parser.add_argument("--gradient-checkpointing", action="store_true",
                        help="그래디언트 체크포인팅으로 활성화 메모리를 줄인다 (속도↓)")
    parser.add_argument("--freeze-encoder", action="store_true", help="decision head만 학습")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true", help="데이터 통계만 출력하고 학습하지 않음")
    parser.add_argument(
        "--skip-prepare", action="store_true",
        help="--out에 이미 준비된 train.jsonl/eval.jsonl을 그대로 쓰고 데이터를 다시 만들지 않음 "
             "(오프라인 재학습용. 네트워크 접속이 필요 없다)")


def main():
    parser = argparse.ArgumentParser(
        description="15개 OHLCV 캔들로 BUY/SELL/HOLD 판단을 학습하는 Laya 파인튜닝 스크립트"
    )
    sub = parser.add_subparsers(dest="command")

    prepare_parser = sub.add_parser("prepare", help="데이터 준비만 수행")
    add_data_args(prepare_parser)

    train_parser = sub.add_parser("train", help="데이터 준비 + Laya 파인튜닝")
    add_data_args(train_parser)
    add_train_args(train_parser)
    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        return

    if args.command == "train" and args.skip_prepare:
        train_path = Path(args.out) / "train.jsonl"
        eval_path = Path(args.out) / "eval.jsonl"
        if not train_path.is_file() or not eval_path.is_file():
            parser.error(
                f"--skip-prepare을 쓰려면 먼저 준비된 데이터가 있어야 합니다: {train_path}와 {eval_path}"
            )
        print(f"--skip-prepare: 기존 데이터셋을 그대로 사용합니다 ({train_path}, {eval_path})")
        run_training(args, train_path, eval_path)
        return

    train_path, eval_path, meta = prepare_dataset(args)

    if args.command == "train":
        run_training(args, train_path, eval_path)


if __name__ == "__main__":
    main()

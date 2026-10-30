from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import torch

from common.contract import DEFAULT_INTERVAL

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_ROOT = BASE_DIR / "models"
OUTPUT_ROOT = BASE_DIR / "outputs"

BASE_MODEL_DIR = MODEL_ROOT / "Laya"
FINETUNED_MODEL_DIR = MODEL_ROOT / "Laya-finance"
TRAINING_OUTPUT_DIR = OUTPUT_ROOT / "laya-trading"
HUB_FALLBACK = "convaiinnovations/laya"

CHECKPOINT_REQUIRED = ("rl_agent_config.json", "model.safetensors", "tokenizer")

APP_NAME = "Laya Trading API"
APP_VERSION = "1.0.0"

API_PREFIX = "/api/v1"


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def resolve_device() -> str:
    requested = os.environ.get("LAYA_DEVICE", "").strip().lower()
    if requested and requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if (
        getattr(torch.backends, "mps", None) is not None
        and torch.backends.mps.is_available()
    ):
        return "mps"
    return "cpu"


def is_checkpoint(path: str | Path) -> bool:
    root = Path(path)
    return root.is_dir() and all((root / name).exists() for name in CHECKPOINT_REQUIRED)


def resolve_model_path() -> str:
    override = os.environ.get("LAYA_MODEL_DIR", "").strip()
    if override:
        return override
    for candidate in (FINETUNED_MODEL_DIR, TRAINING_OUTPUT_DIR, BASE_MODEL_DIR):
        if is_checkpoint(candidate):
            return str(candidate)
    return HUB_FALLBACK


@dataclass(frozen=True)
class Settings:
    model_path: str
    device: str
    log_level: str
    interval: str
    warmup: bool


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        model_path=resolve_model_path(),
        device=resolve_device(),
        log_level=_env_str("LOG_LEVEL", "INFO").upper(),
        interval=_env_str("LAYA_INTERVAL", DEFAULT_INTERVAL),
        warmup=_env_bool("LAYA_WARMUP", True),
    )

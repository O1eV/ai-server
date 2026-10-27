from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import laya
import torch

from app.core.config import CHECKPOINT_REQUIRED, get_settings
from app.core.exceptions import ModelLoadError
from app.core.logging_config import logger
from common.contract import QUESTIONS


@dataclass(frozen=True)
class ModelBundle:
    agent: Any
    device: str
    model_path: str
    questions: Dict[str, Dict[str, Any]]
    loaded_at: datetime

    @property
    def loaded(self) -> bool:
        return self.agent is not None


def load_questions(model_path: str) -> Dict[str, Dict[str, Any]]:
    path = Path(model_path) / "questions.json"
    if not path.exists():
        logger.info("questions.json 없음 → common.contract.QUESTIONS 사용")
        return copy.deepcopy(QUESTIONS)

    try:
        with open(path, encoding="utf-8") as handle:
            questions = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelLoadError(f"questions.json을 읽지 못했습니다: {path}") from exc

    if not isinstance(questions, dict) or not questions:
        raise ModelLoadError(f"questions.json 형식이 올바르지 않습니다: {path}")
    for qid, question in questions.items():
        if not isinstance(question, dict) or "criteria" not in question:
            raise ModelLoadError(f"질문 {qid!r}에 criteria가 없습니다: {path}")

    logger.info(
        "questions.json 로드: %d개 질문 (%s)", len(questions), ", ".join(sorted(questions))
    )
    return questions


def _check_local_checkpoint(model_path: str) -> None:
    if not Path(model_path).is_dir():
        return
    missing = [name for name in CHECKPOINT_REQUIRED if not (Path(model_path) / name).exists()]
    if missing:
        raise ModelLoadError(
            f"체크포인트 구성이 불완전합니다: {model_path} (없음: {', '.join(missing)})"
        )


def load_model_bundle(
    model_path: Optional[str] = None, device: Optional[str] = None
) -> ModelBundle:
    settings = get_settings()
    target = model_path or settings.model_path
    target_device = device or settings.device

    _check_local_checkpoint(target)

    if target_device == "cuda" and not torch.cuda.is_available():
        logger.warning("cuda를 요청했지만 사용할 수 없습니다. laya가 CPU로 폴백할 수 있습니다.")
    elif target_device == "mps" and not torch.backends.mps.is_available():
        logger.warning("mps를 요청했지만 사용할 수 없습니다. laya가 CPU로 폴백할 수 있습니다.")

    logger.info("Laya 모델 로딩 시작: %s (device=%s)", target, target_device)
    try:
        agent = laya.load(target, device=target_device)
    except Exception as exc:
        logger.exception("Laya 모델 로딩 실패: %s", target)
        raise ModelLoadError(f"Laya 모델을 로드하지 못했습니다: {target} ({exc})") from exc

    questions = load_questions(target)

    logger.info("Laya 모델 로딩 완료: %s (device=%s)", target, target_device)
    return ModelBundle(
        agent=agent,
        device=target_device,
        model_path=str(target),
        questions=questions,
        loaded_at=datetime.now(timezone.utc),
    )


__all__ = ["ModelBundle", "load_model_bundle", "load_questions"]

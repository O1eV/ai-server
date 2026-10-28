from __future__ import annotations

import os
import secrets

from fastapi import Header

from app.core.exceptions import UnauthorizedError
from app.core.logging_config import logger

API_KEY_ENV = "MODEL_API_KEY"
API_KEY_HEADER = "X-API-KEY"

_warned_unset = False


def _configured_key() -> str:
    # 요청마다 환경변수를 읽는다(테스트와 키 교체가 쉽다). 값은 로그에 남기지 않는다.
    return os.environ.get(API_KEY_ENV, "").strip()


def verify_api_key(x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER)) -> None:
    """/predict 호출자가 Spring 서버인지 X-API-KEY 헤더로 확인한다.

    MODEL_API_KEY가 없으면 로컬 개발 편의를 위해 통과시키되 경고를 남긴다.
    키가 있는데 헤더가 없거나 다르면 401이다. 비교는 시간 차이로 키를 추측하지 못하게 상수 시간으로 한다.
    """
    global _warned_unset

    expected = _configured_key()
    if not expected:
        if not _warned_unset:
            logger.warning("%s가 설정되지 않아 /predict 인증 없이 동작합니다. 배포 환경에서는 반드시 설정하세요.", API_KEY_ENV)
            _warned_unset = True
        return

    if not x_api_key or not secrets.compare_digest(x_api_key.encode(), expected.encode()):
        raise UnauthorizedError("유효한 X-API-KEY가 필요합니다.")

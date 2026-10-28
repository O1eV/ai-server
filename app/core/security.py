from __future__ import annotations

import os
import secrets

from fastapi import Header

from app.core.exceptions import UnauthorizedError
from app.core.logging_config import logger

API_KEY_ENV = "MODEL_API_KEY"
ALLOW_INSECURE_ENV = "ALLOW_INSECURE_NO_AUTH"
API_KEY_HEADER = "X-API-KEY"

_warned_insecure = False


def _configured_key() -> str:
    # 요청마다 환경변수를 읽는다(테스트와 키 교체가 쉽다). 값은 로그에 남기지 않는다.
    return os.environ.get(API_KEY_ENV, "").strip()


def _insecure_allowed() -> bool:
    return os.environ.get(ALLOW_INSECURE_ENV, "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def verify_api_key(
    x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER),
) -> None:
    """/predict 호출자가 Spring 서버인지 X-API-KEY 헤더로 확인한다.

    기본은 fail-closed다. MODEL_API_KEY가 없거나 비어 있으면 모든 요청이 401이다.
    로컬 개발에서만 ALLOW_INSECURE_NO_AUTH=1로 명시적으로 인증을 끌 수 있다(경고를 1회 남긴다).
    키가 있는데 헤더가 없거나 비었거나 다르면 401이다. 비교는 상수 시간으로 한다.
    """
    global _warned_insecure

    expected = _configured_key()
    if not expected:
        if _insecure_allowed():
            if not _warned_insecure:
                logger.warning(
                    "%s=1 이므로 /predict 인증 없이 동작합니다. 로컬 개발에서만 쓰세요.",
                    ALLOW_INSECURE_ENV,
                )
                _warned_insecure = True
            return
        logger.error("%s가 설정되지 않아 /predict 요청을 거부합니다.", API_KEY_ENV)
        raise UnauthorizedError("서버에 API 키가 설정되지 않았습니다.")

    if not x_api_key or not secrets.compare_digest(
        x_api_key.encode(), expected.encode()
    ):
        raise UnauthorizedError("유효한 X-API-KEY가 필요합니다.")

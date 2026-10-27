from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.core.exceptions import ModelNotLoadedError
from app.core.model_loader import ModelBundle


def get_model_bundle(request: Request) -> ModelBundle:
    bundle = getattr(request.app.state, "model_bundle", None)

    if bundle is None:
        raise ModelNotLoadedError("Laya 모델이 로드되지 않았습니다.")

    return bundle


ModelBundleDep = Annotated[ModelBundle, Depends(get_model_bundle)]

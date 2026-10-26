from __future__ import annotations

from typing import Dict

from fastapi import APIRouter

from app.core.dependencies import ModelBundleDep

router = APIRouter(tags=["model"])


@router.get("/model/status")
def get_model_status(bundle: ModelBundleDep) -> Dict[str, object]:
    return {
        "loaded": bundle.loaded,
        "device": bundle.device,
        "model_path": bundle.model_path,
        "questions": sorted(bundle.questions),
        "loaded_at": bundle.loaded_at.isoformat(),
    }


__all__ = ["router"]

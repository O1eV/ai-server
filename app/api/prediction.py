from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from app.core.dependencies import ModelBundleDep
from app.core.security import verify_api_key
from app.dto.request.stock_data import StockData
from app.dto.response.stock_decision import Decision
from app.services.prediction import predict

router = APIRouter(tags=["prediction"], dependencies=[Depends(verify_api_key)])


@router.post("/predict", response_model=Decision)
def predict_endpoint(candles: List[StockData], bundle: ModelBundleDep) -> Decision:
    return predict(candles, bundle)

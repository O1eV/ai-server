from __future__ import annotations


class LayaError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.__class__.__name__)


class ModelLoadError(LayaError):
    status_code = 503
    code = "model_load_failed"


class ModelNotLoadedError(LayaError):
    status_code = 503
    code = "model_not_loaded"


class PredictionError(LayaError):
    status_code = 500
    code = "prediction_failed"


class InvalidMarketDataError(LayaError):
    status_code = 422
    code = "invalid_market_data"

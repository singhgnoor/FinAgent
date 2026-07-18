import math
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, field_validator


class SignalRequest(BaseModel):
    signal_type: Literal["price_tick", "news_text", "document"]
    payload: Dict[str, Any]
    source: str = "api"


class PriceTickRequest(BaseModel):
    asset: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: Optional[datetime] = None

    @field_validator("open", "high", "low", "close", "volume")
    @classmethod
    def finite_number(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("must be a finite number")
        return value


class NewsRequest(BaseModel):
    headline: str
    summary: Optional[str] = None
    full_text: Optional[str] = None
    asset: Optional[str] = None

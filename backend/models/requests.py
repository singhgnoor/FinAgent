from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel


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


class NewsRequest(BaseModel):
    headline: str
    summary: Optional[str] = None
    full_text: Optional[str] = None
    asset: Optional[str] = None

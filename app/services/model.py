"""Domain models shared across UI layers."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class BalanceAsset(BaseModel):
    asset: str
    free: float
    used: float
    total: float
    quote_price: Optional[float] = None

    @property
    def value(self) -> float:
        """Quote‑denominated value of this asset (0 if price missing)."""
        return (self.total or 0) * (self.quote_price or 0)


class BalanceSnapshot(BaseModel):
    equity_quote: float = Field(..., alias="equityQuote")
    assets: list[BalanceAsset]


class Order(BaseModel):
    id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    type: str
    price: float
    qty: float
    filled: float
    status: str
    ts: datetime
import requests, pandas as pd
from app.config import settings
from app.services.model import BalanceSnapshot, Order

HEAD = {"x-api-key": settings()["API_KEY"]}
BASE = settings()["API_URL"]


def _get(path: str):
    r = requests.get(f"{BASE}{path}", headers=HEAD, timeout=3)
    r.raise_for_status(); return r.json()


def get_balance() -> dict:
    bal_raw = _get("/balance")
    assets_raw = _get("/balance/list")

    snapshot = BalanceSnapshot(**bal_raw, assets=[*assets_raw])  # type: ignore[arg-type]
    assets_df = pd.DataFrame([a.model_dump() for a in snapshot.assets])
    return {"equity": snapshot.equity_quote, "assets_df": assets_df}


def get_orders(status: str = "open") -> pd.DataFrame:
    rows = _get(f"/orders?status={status}")
    orders = [Order(**row) for row in rows]
    return pd.DataFrame([o.model_dump() for o in orders])
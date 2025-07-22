# app/services/api.py
import requests, pandas as pd
from app.config import settings

HEAD, BASE = {"x-api-key": settings()["API_KEY"]}, settings()["API_URL"]
QUOTE  = settings()["QUOTE_ASSET"]

def _get(path: str):
    r = requests.get(f"{BASE}{path}", headers=HEAD, timeout=3)
    r.raise_for_status()
    return r.json()

def _prices_for(assets: list[str]) -> dict[str, float]:
    """
    Return {asset: last_price_in_quote}.
    Works with mock-exchange `/tickers/BTC/USDT,ETH/USDT`
    and with list-style payloads from a future /ticker/price alias.
    """
    pairs = [f"{a}/{QUOTE}" for a in assets if a != QUOTE]           # e.g. BTC/USDT
    res   = _get(f"/tickers/{','.join(pairs)}")                     # dict OR list

    def _extract_price(d: dict) -> float | None:
        """pull price from whatever key the exchange uses."""
        if "last" in d:                 # normal CCXT ticker
            return float(d["last"])
        if "info" in d and "price" in d["info"]:
            return float(d["info"]["price"])
        return None                     # unknown shape → skip

    price_map = {}

    if isinstance(res, dict):           # { "BTC/USDT": {...}, ... }
        for data in res.values():
            p = _extract_price(data)
            if p is not None:
                price_map[data["symbol"].split("/")[0]] = p

    elif isinstance(res, list):         # [ {...}, {...} ]
        for data in res:
            p = _extract_price(data)
            if p is not None and "symbol" in data:
                price_map[data["symbol"].split("/")[0]] = p
    else:
        raise TypeError(f"Unexpected ticker payload type: {type(res)}")
    
    # Add quote 1:1 price for the quote asset itself
    if QUOTE not in price_map:
        price_map[QUOTE] = 1.0

    return price_map

def _extract_assets(raw):
    """
    Normalise whatever `/balance` returns into a list[dict].
    Accepts:
        1. {"assets": [...]}
        2. {"data": [...]}
        3. {"balances": [...]}
        4. [{"asset": "BTC", ...}, ...]          # plain list
        5. {"BTC": {...}, "ETH": {...}}          # mapping asset→fields
    """
    if isinstance(raw, list):
        return raw                                              # #4

    if isinstance(raw, dict):
        for key in ("assets", "data", "balances"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]                                 # #1-3

        # #5 mapping style: turn into list of dicts
        if all(isinstance(v, dict) for v in raw.values()):
            return [{"asset": k, **v} for k, v in raw.items()]

    raise ValueError("Unrecognised `/balance` payload shape")

def get_balance() -> dict:
    """Fetch `/balance` endpoint and return a dict with:
    - equity: total value in quote asset
    - quote_asset: the quote asset symbol (e.g. USDT)
    - assets_df: DataFrame with asset balances, prices, and values.
    """
    snap = _get("/balance")
    if len(snap) == 0:
        return {
            "equity": 0.0,
            "quote_asset": settings()["QUOTE_ASSET"],
            "assets_df": pd.DataFrame(),
        }
    
    assets_df = pd.DataFrame(_extract_assets(snap))

    # Ensure essential columns exist -----------------------------------------
    if "asset" not in assets_df.columns:
        raise KeyError("`/balance` response lacks an 'asset' column")

    if "total" not in assets_df.columns:
        # derive 'total' from free+locked or just free
        free  = assets_df.get("free")
        locked = assets_df.get("locked", 0)
        if free is not None:
            assets_df["total"] = free + locked
        else:
            raise KeyError("Neither 'total' nor 'free' present in balance data")

    # Price enrichment --------------------------------------------------------
    if "quote_price" not in assets_df.columns:
        price_map = _prices_for(assets_df["asset"].tolist())
        assets_df["quote_price"] = assets_df["asset"].map(price_map)

    equity = (assets_df["total"] * assets_df["quote_price"]).sum()

    return {
        "equity": equity,
        "quote_asset": settings()["QUOTE_ASSET"],
        "assets_df": assets_df,
    }

def get_active_asset_count() -> int:
    """Thin helper for places that only need the tally shown by `/balance/list`."""
    return _get("/balance/list")["count"]

def get_orders(status: str | None = None, tail: int = 50) -> pd.DataFrame:
    """
    Fetch recent orders from `/orders` endpoint and return a tidy DataFrame.

    Args:
        status: 'open', 'filled', 'canceled', … or None for all.
        tail:  max tail rows to pull.

    The endpoint is expected to return a JSON list of dicts, each at least:
        { "id": "...", "asset": "BTC", "side": "BUY", "qty": 0.1,
          "price": 45000, "status": "FILLED", "timestamp": 1713187200 }
    """
    params = []
    if status:
        params.append(f"status={status}")
    if tail:
        params.append(f"tail={tail}")
    path = "/orders" + ("?" + "&".join(params) if params else "")
    rows = _get(path)                       # <- uses the existing private helper
    return pd.DataFrame(rows)
"""_helpers.py

Utility helpers shared by multiple Streamlit pages.

The module groups three kinds of helpers:

1. **Formatting helpers** – e.g. `_remove_small_zeros` to strip trailing
   insignificant zeros from decimal strings.
2. **DataFrame enrichment** – `_add_details_column` injects a hyperlink
   column so each order row can point to its *Order Details* popup.
3. **Advanced equity display** – `_display_advanced_details` pulls a
   balance-vs-orderbook summary from the API and shows it as Streamlit
   metrics, highlighting mismatches with a warning icon.

Only **docstrings and comments** have been added; no functional changes.
"""

from __future__ import annotations

# Third-party -----------------------------------------------------------------
import math
import pandas as pd
import streamlit as st

# Project ---------------------------------------------------------------------
from app.services.api import get_assets_overview, get_trades_overview

# -----------------------------------------------------------------------------
# 1) Formatting helpers
# -----------------------------------------------------------------------------

ZERO_DISPLAY = "--"  # Default display for zero values

def _remove_small_zeros(num_str: str) -> str:  # noqa: D401 – short desc fine
    """Strip redundant trailing zeros from a *decimal* string.

    Examples
    --------
    >>> _remove_small_zeros('1.230000')
    '1.23'
    >>> _remove_small_zeros('42.000')
    '42'

    Notes
    -----
    The function assumes the input is already formatted to the desired
    decimal precision (typically 6 d.p. in this app) and only performs a
    *pure string* operation – no rounding is applied.
    """
    try:
        # ``rstrip`` twice: first remove zeros, then a dangling decimal point.
        return num_str.rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        # Fall back to the original string if parsing fails (e.g. None).
        return num_str

# -----------------------------------------------------------------------------
# 2) DataFrame manipulation helpers
# -----------------------------------------------------------------------------

def _add_details_column(
    df: pd.DataFrame,
    base_url: str,
    *,
    order_id_col: str = "id",
    new_col: str = "Details",
    path_template: str = "?order_id={oid}&page=Orders",
    text: str = "🔍",
) -> pd.DataFrame:  # noqa: D401 – keep same signature
    """Append a column with **HTML links** to the order-details page.

    Parameters
    ----------
    df : pd.DataFrame
        Input frame; *must* contain ``order_id_col``.
    base_url : str
        Base URL where the Streamlit app is served (currently unused but
        kept for future external links).
    order_id_col : str, default ``"id"``
        Column name holding order IDs.
    new_col : str, default ``"Details"``
        Name of the column to add.
    path_template : str
        Relative URL pattern where ``{oid}`` is interpolated – keeps the
        user in the same tab.
    text : str, default "🔍"
        Anchor text / icon for the hyperlink.

    Returns
    -------
    pd.DataFrame
        *Copy* of the original with an extra column of raw ``<a href>``
        strings – suitable for ``styler.format(escape="html")`` to render.
    """
    df = df.copy()

    def make_url(oid: str) -> str:
        # Example →  "?order_id=123&page=Orders"
        return path_template.format(oid=oid)

    if not df.empty:
        df[new_col] = df[order_id_col].astype(str).map(make_url)
    return df

def _format_significant_float(value: float | int | None, unity: str | None = None) -> str:
    """
    Format a float into a human-readable string with dynamic precision.

    Behavior:
    - For absolute values >= 1: formats with comma as thousands separator and 2 decimal places.
      Example:  1234.6565  → "1,234.66"
                -1234.6565 → "-1,234.66"

    - For absolute values < 1: keeps leading zeros and shows the first 2 significant decimal digits.
      Example:  
                0.6565     → "0.66"
               -0.06565    → "-0.066"
                0.006565   → "0.0066"
               -0.0006565  → "-0.00066"

    - For exact zero (positive or negative): returns a fixed display (e.g. "0.00")

    Args:
        value (float | int | None): The number to format.
        unity (str | None): Optional unit/currency suffix (e.g., "USD").

    Returns:
        str: The formatted number as a string.
    """
    if value is None or pd.isna(value) or value == 0.0:
        return ZERO_DISPLAY

    is_negative = value < 0
    abs_value = abs(value)

    if abs_value >= 1:
        formatted = f"{abs_value:,.2f}"
    else:
        # true “round to two significant digits”:
        # floor(log10(abs_value)) gives you the exponent of the leading sig‑digit.
        exp = math.floor(math.log10(abs_value))
        decimals = 2 - exp - 1
        rounded = round(abs_value, decimals)
        formatted = f"{rounded:.{decimals}f}"

    if is_negative:
        formatted = "-" + formatted
    if unity:
        formatted += f" {unity}"

    return formatted


fmt_side_marker = lambda side: {"BUY": "↗ BUY", "SELL": "↘ SELL"}[side.upper()]  # noqa: E731

# -----------------------------------------------------------------------------
# 3) Advanced equity breakdown helper
# -----------------------------------------------------------------------------

_W = "⚠️"  # warning icon – reused inline for brevity

def _display_advanced_details() -> None:  # noqa: D401
    """Show an advanced *equity vs frozen* breakdown in three metric columns.

    Fetches the combined summary from ``/overview/assets`` (via
    ``get_assets_overview``), then prints a grid of **st.metric** widgets
    comparing *portfolio* vs *order-book* numbers.  Any mismatch is
    flagged with a warning icon (⚠️) in front of the figure.
    """

    summary = get_assets_overview()
    misc = summary.get("misc", {})
    cash_asset = misc.get("cash_asset", "")
    mismatch = misc.get("mismatch", {})  # dict[field -> bool]

    # Local lambdas for consistent formatting ---------------------------
    fmt_cash = lambda v: f"{v:,.2f} {cash_asset}"  # noqa: E731
    fmt = (
        lambda txt, w: f"{_W} {fmt_cash(txt)}" if w else fmt_cash(txt)
    )  # noqa: E731 – add warning icon when mismatch True

    balance_summary = summary.get("balance_source", {})
    orders_summary = summary.get("orders_source", {})

    # ------------------------------------------------------------------
    # Render three metric columns (equity / cash / assets)
    # ------------------------------------------------------------------
    c1, c2, c3 = st.columns(3)

    # Equity ------------------------------------------------------------
    with c1:
        st.metric("Portfolio ▶ Total equity", fmt(balance_summary["total_equity"], False))
        st.metric("Portfolio ▶ Free equity", fmt(balance_summary["total_free_value"], False))
        st.metric(
            "Portfolio ▶ Frozen equity",
            fmt(balance_summary["total_frozen_value"], mismatch["total_frozen_value"]),
        )
        st.metric(
            "Order book ▶ Frozen equity",
            fmt(orders_summary["total_frozen_value"], mismatch["total_frozen_value"]),
        )

    # Cash --------------------------------------------------------------
    with c2:
        st.metric("Portfolio ▶ Total cash", fmt(balance_summary["cash_total_value"], False))
        st.metric("Portfolio ▶ Free cash", fmt(balance_summary["cash_free_value"], False))
        st.metric(
            "Portfolio ▶ Frozen cash",
            fmt(balance_summary["cash_frozen_value"], mismatch["cash_frozen_value"]),
        )
        st.metric(
            "Order book ▶ Frozen cash",
            fmt(orders_summary["cash_frozen_value"], mismatch["cash_frozen_value"]),
        )

    # Assets ------------------------------------------------------------
    with c3:
        st.metric(
            "Portfolio ▶ Total assets value",
            fmt(balance_summary["assets_total_value"], False),
        )
        st.metric(
            "Portfolio ▶ Free assets value",
            fmt(balance_summary["assets_free_value"], False),
        )
        st.metric(
            "Portfolio ▶ Frozen assets value",
            fmt(balance_summary["assets_frozen_value"], mismatch["assets_frozen_value"]),
        )
        st.metric(
            "Order book ▶ Frozen assets value",
            fmt(orders_summary["assets_frozen_value"], mismatch["assets_frozen_value"]),
        )

def _display_advanced_trades() -> None:  # noqa: D401
    """
    Show an advanced *trades summary* in three metric columns.

    Fetches the combined summary from ``/overview/trades`` (via
    ``get_trades_overview``), then prints a grid of **st.metric** widgets
    comparing *total*, *buy*, and *sell* trades.  Any mismatch in the
    total amount is flagged with a warning icon (⚠️) in front of the figure.
    """

    trades_summary, cash_asset= get_trades_overview()

    # Local lambdas for consistent formatting ---------------------------
    fmt_num = lambda v: f"{v:,.0f}"  # noqa: E731
    fmt_cash = lambda v: f"{v:,.2f} {cash_asset}"  # noqa: E731
    fmt_cash_w = (
        lambda txt, w: f"{_W} {fmt_cash(txt)}" if w else fmt_cash(txt)
    )  # noqa: E731 – add warning icon when mismatch True

    # ------------------------------------------------------------------
    # Render three metric columns (equity / cash / assets)
    # ------------------------------------------------------------------
    c1, c2, c3 = st.columns(3)

    # Total trades ------------------------------------------------------------
    with c1:
        st.metric("Trades ▶ Total Count", fmt_num(trades_summary["TOTAL"]["count"]))
        st.metric("Value ▶ Total Amount (Current Price)", fmt_cash_w(trades_summary["TOTAL"]["amount_value"], trades_summary["TOTAL"]["amount_value_incomplete"]))
        st.metric("Notional ▶ Total", fmt_cash(trades_summary["TOTAL"]["notional"]))
        st.metric("Fees ▶ Total", fmt_cash(trades_summary["TOTAL"]["fee"]))

    # Buy trades --------------------------------------------------------------
    with c2:
        st.metric("Trades ▶ Buy Count", fmt_num(trades_summary["BUY"]["count"]))
        st.metric("Value ▶ Buy Amount (Current Price)", fmt_cash_w(trades_summary["BUY"]["amount_value"], trades_summary["BUY"]["amount_value_incomplete"]))
        st.metric("Notional ▶ Buy", fmt_cash(trades_summary["BUY"]["notional"]))
        st.metric("Fees ▶ Buy", fmt_cash(trades_summary["BUY"]["fee"]))

    # Sell trades ------------------------------------------------------------
    with c3:
        st.metric("Trades ▶ Sell Count", fmt_num(trades_summary["SELL"]["count"]))
        st.metric("Value ▶ Sell Amount (Current Price)", fmt_cash_w(trades_summary["SELL"]["amount_value"], trades_summary["SELL"]["amount_value_incomplete"]))
        st.metric("Notional ▶ Sell", fmt_cash(trades_summary["SELL"]["notional"]))
        st.metric("Fees ▶ Sell", fmt_cash(trades_summary["SELL"]["fee"]))

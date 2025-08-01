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
_W = "⚠️"  # warning icon – reused inline for brevity


# Local lambdas for consistent formatting ---------------------------
fmt_num = lambda v, warning = False: f"{v:,.0f}" if not warning else f"^{_W} {v:,.0f}"
fmt_percent = lambda v, warning = False: f"{v:.2%}" if not warning else f"^{_W} {v:.2%}"
fmt_cash = lambda v, cash_asset, warning = False: f"{v:,.2f} {cash_asset}" if not warning else f"^{_W} {v:,.2f} {cash_asset}"
# fmt_cash_w = (
#     lambda txt, w, cash_asset: f"^{_W} {fmt_cash(txt, cash_asset)}" if w else fmt_cash(txt, cash_asset)
# )  # noqa: E731 – add warning icon when mismatch True

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

def _display_advanced_portfolio() -> None:  # noqa: D401
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

    balance_summary = summary.get("balance_source", {})
    orders_summary = summary.get("orders_source", {})

    # ------------------------------------------------------------------
    # Render three metric columns (equity / cash / assets)
    # ------------------------------------------------------------------
    c1, c2, c3 = st.columns(3)
    st.markdown("---")

    # Equity ------------------------------------------------------------
    with c1:
        st.metric("Portfolio ▶ Total equity", fmt_cash(balance_summary["total_equity"], cash_asset))
        st.metric("Portfolio ▶ Free equity", fmt_cash(balance_summary["total_free_value"], cash_asset))
        st.metric(
            "Portfolio ▶ Frozen equity",
            fmt_cash(balance_summary["total_frozen_value"], cash_asset, mismatch["total_frozen_value"]),
        )
        st.metric(
            "Order book ▶ Frozen equity",
            fmt_cash(orders_summary["total_frozen_value"], cash_asset, mismatch["total_frozen_value"]),
        )

    # Cash --------------------------------------------------------------
    with c2:
        st.metric("Portfolio ▶ Total cash", fmt_cash(balance_summary["cash_total_value"], cash_asset))
        st.metric("Portfolio ▶ Free cash", fmt_cash(balance_summary["cash_free_value"], cash_asset))
        st.metric(
            "Portfolio ▶ Frozen cash",
            fmt_cash(balance_summary["cash_frozen_value"], cash_asset, mismatch["cash_frozen_value"]),
        )
        st.metric(
            "Order book ▶ Frozen cash",
            fmt_cash(orders_summary["cash_frozen_value"], cash_asset, mismatch["cash_frozen_value"]),
        )

    # Assets ------------------------------------------------------------
    with c3:
        st.metric(
            "Portfolio ▶ Total assets value",
            fmt_cash(balance_summary["assets_total_value"], cash_asset),
        )
        st.metric(
            "Portfolio ▶ Free assets value",
            fmt_cash(balance_summary["assets_free_value"], cash_asset),
        )
        st.metric(
            "Portfolio ▶ Frozen assets value",
            fmt_cash(balance_summary["assets_frozen_value"], cash_asset, mismatch["assets_frozen_value"]),
        )
        st.metric(
            "Order book ▶ Frozen assets value",
            fmt_cash(orders_summary["assets_frozen_value"], cash_asset, mismatch["assets_frozen_value"]),
        )

def _display_basic_trades_details(trades_summary: dict, cash_asset:str) -> None:
    """
    Show a basic *trades summary* in three metric columns.

    Fetches the combined summary from ``/overview/trades`` (via
    ``get_trades_overview``), then prints a grid of **st.metric** widgets
    comparing *total*, *buy*, and *sell* trades.  Any mismatch in the
    total amount is flagged with a warning icon (⚠️) in front of the figure.
    """

    # --- core amounts --------------------------------------------------
    incomplete_data        = trades_summary["TOTAL"]["amount_value_incomplete"]
    total_investment       = trades_summary["BUY"]["notional"]
    total_divestment       = trades_summary["SELL"]["notional"]
    actual_investment      = total_investment - total_divestment
    total_paid_fees        = trades_summary["TOTAL"]["fee"]

    buy_current_value      = trades_summary["BUY"]["amount_value"] # Current value of all buy trades - even if part of them have already been sold
    sell_current_value     = trades_summary["SELL"]["amount_value"] # Current value of all sell trades - somehow is the missing opportunity value
    assets_current_value   = buy_current_value - sell_current_value # still held

    # --- cash & P&L figures -------------------------------------------
    gross_earnings         = assets_current_value - actual_investment  # before fees
    net_earnings           = gross_earnings - total_paid_fees  # after fees
    market_value_open      = assets_current_value

    # --- ROI on current risk ------------------------------------------
    gross_roi_on_cost      = gross_earnings / actual_investment if actual_investment > 0 else None  # before fees
    net_roi_on_cost        = net_earnings / actual_investment if actual_investment > 0 else None # after fees
    gross_roi_on_value     = gross_earnings / assets_current_value if assets_current_value > 0 else None # before fees
    net_roi_on_value       = net_earnings / assets_current_value if assets_current_value > 0 else None # after fees

    # --- multiples (gross) --------------------------------------------
    total_investment = total_investment if total_investment or total_investment > 0 else None  # avoid division by zero

    # --- multiples (gross) --------------------------------------------
    dpi_gross  = total_divestment / total_investment if total_investment else None # DPI = Distributions to Paid-In
    rvpi_gross = assets_current_value / total_investment if total_investment else None # RVPI = Residual Value to Paid-In
    moic_gross = dpi_gross + rvpi_gross if None not in (dpi_gross, rvpi_gross) else None # MOIC = Multiple on Invested Capital

    # Total trades ------------------------------------------------------------
    # ------------------------------------------------------------------
    # Render three metric columns
    # ------------------------------------------------------------------
    c1, c2, c3 = st.columns(3)

    # ────────────────────────────────────────────────────────────────
    # Column 1 · Cash & P&L figures
    # ────────────────────────────────────────────────────────────────
    with c1:
        st.metric(
            "Value ▶ Open Positions",
            fmt_cash(market_value_open, cash_asset, incomplete_data)
        )
        st.metric(
            "P&L ▶ Net (After Fees)",
            fmt_cash(net_earnings, cash_asset, incomplete_data)
        )
        st.metric(
            "P&L ▶ Gross (Before Fees)",
            fmt_cash(gross_earnings, cash_asset, incomplete_data)
        )

    # ────────────────────────────────────────────────────────────────
    # Column 2 · ROI on current risk
    # ────────────────────────────────────────────────────────────────
    with c2:
        display_roi = True
        if actual_investment > 0:
            net_roi_title = "ROI ▶ Net on Cost"
            net_roi = net_roi_on_cost
            gross_roi_title = "ROI ▶ Gross on Cost"
            gross_roi = gross_roi_on_cost
        elif assets_current_value > 0:
            # If no investment was made, but we have a current value,
            # show ROI on that value instead.
            display_roi = True
            net_roi_title = "ROI ▶ Net on Value"
            net_roi = net_roi_on_value
            gross_roi_title = "ROI ▶ Gross on Value"
            gross_roi = gross_roi_on_value
        else:
            display_roi = False

        st.metric(
            "Capital ▶ At Risk (Cost)",
            fmt_cash(actual_investment, cash_asset, incomplete_data)
        )
        if not display_roi:
            st.warning(
                "No ROI data available. "
                "Either no trades were made or the current value is zero."
            )
        else:
            # Show ROI metrics only if we have a valid investment or current value.
            st.metric(
                net_roi_title,
                fmt_percent(net_roi, incomplete_data) if net_roi is not None else ZERO_DISPLAY
            )
            st.metric(
                gross_roi_title,
                fmt_percent(gross_roi, incomplete_data) if gross_roi is not None else ZERO_DISPLAY
            )

    # ────────────────────────────────────────────────────────────────
    # Column 3 · Multiples as % returns (0 % = break-even)
    # ────────────────────────────────────────────────────────────────
    with c3:
        st.metric(
            "Multiple ▶ RVPI (Residual Value to Paid-In)",
            fmt_percent(rvpi_gross, incomplete_data) if rvpi_gross is not None else ZERO_DISPLAY
        )
        st.metric(
            "Multiple ▶ DPI (Distributions to Paid-In)",
            fmt_percent(dpi_gross, incomplete_data) if dpi_gross is not None else ZERO_DISPLAY
        )
        st.metric(
            "Multiple ▶ MOIC (Multiple on Invested Capital)",
            fmt_percent(moic_gross, incomplete_data) if moic_gross is not None else ZERO_DISPLAY
        )

def _display_advanced_trades(trades_summary: dict, cash_asset:str) -> None:  # noqa: D401
    """
    Show an advanced *trades summary* in three metric columns.

    Fetches the combined summary from ``/overview/trades`` (via
    ``get_trades_overview``), then prints a grid of **st.metric** widgets
    comparing *total*, *buy*, and *sell* trades.  Any mismatch in the
    total amount is flagged with a warning icon (⚠️) in front of the figure.
    """

    # Display_basic_trades_details(trades_summary, cash_asset)
    _display_basic_trades_details(trades_summary, cash_asset)

    total_investment = trades_summary["BUY"]["notional"]
    total_divestment = trades_summary["SELL"]["notional"]
    total_traded = total_investment + total_divestment
    count_buy_orders = trades_summary["BUY"]["count"]
    count_sell_orders = trades_summary["SELL"]["count"]
    total_orders = trades_summary["TOTAL"]["count"]
    avg_buy_price_order = total_investment / count_buy_orders if count_buy_orders > 0 else 0
    avg_sell_price_order = total_divestment / count_sell_orders if count_sell_orders > 0 else 0
    avg_trade_price_order = total_traded / total_orders if total_orders > 0 else 0
    # ------------------------------------------------------------------
    # Render three metric columns (equity / cash / assets)
    # ------------------------------------------------------------------
    st.markdown("---")
    c1, c2, c3 = st.columns(3)

    # -----------------------------------------------------------------
    # Column 1 · All orders
    # -----------------------------------------------------------------
    with c1:
        st.metric("Notional ▶ Traded (All)",         fmt_cash(total_traded, cash_asset))
        st.metric("Orders   ▶ Count (All)",          fmt_num(total_orders))
        st.metric("Avg. Order Size ▶ All",            fmt_cash(avg_trade_price_order, cash_asset))
        st.metric("Fees     ▶ Paid (All)",           fmt_cash(trades_summary["TOTAL"]["fee"], cash_asset))

    # -----------------------------------------------------------------
    # Column 2 · Buy side
    # -----------------------------------------------------------------
    with c2:
        st.metric("Notional ▶ Invested (Buy)",       fmt_cash(total_investment, cash_asset))
        st.metric("Orders   ▶ Count (Buy)",          fmt_num(count_buy_orders))
        st.metric("Avg. Order Size ▶ Buy",            fmt_cash(avg_buy_price_order, cash_asset))
        st.metric("Fees     ▶ Paid (Buy)",           fmt_cash(trades_summary["BUY"]["fee"], cash_asset))

    # -----------------------------------------------------------------
    # Column 3 · Sell side
    # -----------------------------------------------------------------
    with c3:
        st.metric("Notional ▶ Divested (Sell)",      fmt_cash(total_divestment, cash_asset))
        st.metric("Orders   ▶ Count (Sell)",         fmt_num(count_sell_orders))
        st.metric("Avg. Order Size ▶ Sell",           fmt_cash(avg_sell_price_order, cash_asset))
        st.metric("Fees     ▶ Paid (Sell)",          fmt_cash(trades_summary["SELL"]["fee"], cash_asset))

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
from typing import Literal
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

# -------------------------------------------------------------------------
# 3) Streamlit metric helpers  (paste into _helpers.py or a new utils_metrics.py)
# -------------------------------------------------------------------------

def _mk_key(label: str) -> str:
    """Stable session-state key from the metric label."""
    return f"_prev_{label.replace(' ', '_').lower()}"

def show_metric(
    label: str,
    value: float | None,
    *,
    value_type: Literal["integer", "percent", "normal"] = "normal",
    unit: str = "",
    incomplete: bool = False,
    # delta options ---------------------------------------------------
    baseline: float | None = None,          # None  → compare to last run
    delta_fmt: Literal["raw", None] = "raw",
    delta_color_rule: Literal["value", "delta"] = "value",
    # value-colour options -------------------------------------------
    neutral_100: bool = False,              # treat <1 as red
    bad_if_neg: bool = True,
    incomplete_display: bool = False,         # Metric to display when incomplete occurs
) -> None:
    """
    Print one st.metric with colour & delta handled.

    Parameters
    ----------
    label : str
        Label shown above the number.
    value : float | None
        Latest value. None → prints ZERO_DISPLAY and skips delta.
    value_type: Literal["integer", "percent", "normal"]
        How to format the main value.
    unit : str
        Suffix (e.g. "€", "×", "%", "USDT").
    incomplete : bool
        If True, show ⚠️ icon before the figure.
    baseline : float | None
        Reference value. If None, use the value stored in session_state.
    delta_fmt : Literal["raw", "percent", None]
        How to format the delta column.
    delta_color_rule : Literal["value", "delta"]
        • "value"  → red/green based on *value* (e.g. multiples <1 red)
        • "delta"  → red/green based on *delta* sign.
    neutral_100 : bool
        Treat 100% as break-even when colouring the value.
    bad_if_neg : bool
        For non-multiple values: colour red if value < 0.
    incomplete_display : bool
        Records with True, will only be displayed if incomplete is True.
    """
    # ---- format main value -----------------------------------------
    if value is None:
        txt_value = ZERO_DISPLAY
    else:
        if value_type == "integer":
            txt_value = f"{value:,.0f}{unit}"
        elif value_type == "percent":
            if abs(value) < 2:
                # When value is less than 2% it is shown as a percentage
                txt_value = f"{value:,.2%}"
            else:
                # When value is greater than 2% it is shown as a multiple
                txt_value = f"{value:,.2f}×"

        elif value_type == "normal":
            txt_value = f"{value:,.2f}{unit}"
        else:
            raise ValueError(f"Unknown value_type: {value_type}")
        if incomplete:
            txt_value = f"{_W} {txt_value}"
    # ---- compute & format delta ------------------------------------
    delta_raw = None
    key = _mk_key(label)
    ref = baseline if baseline is not None else st.session_state.get(key)

    if value is not None and ref is not None and delta_fmt:
        delta_raw = value - ref
        if delta_fmt == "raw":
            if value_type == "integer":
                delta_display = f"{delta_raw:+,.0f}{unit}"
            elif value_type == "percent":
                delta_display = f"{delta_raw:+,.2%}"
            elif value_type == "normal":
                delta_display = f"{delta_raw:+,.2f}{unit}"
        else:
            delta_display = None
    else:
        delta_display = None

    # ---- decide arrow colour ---------------------------------------
    if delta_display is None:
        delta_color = "off"
    elif delta_color_rule in ("normal", "inverse"):
        delta_color = delta_color_rule
    else:
        delta_color = "off"  # default to off if unknown

    # ---- store for next call ---------------------------------------
    st.session_state[key] = value

    # ---- render -----------------------------------------------------
    if incomplete_display:
        if not incomplete:
            return  # skip rendering if incomplete is False
        # If incomplete is True, show the incomplete_display value.
    st.metric(label, txt_value, delta_display, delta_color=delta_color)

def show_metrics_bulk(column, specs: list[dict]) -> None:
    """
    Print a list of metrics into the given Streamlit *column*.

    specs = [
        {"label": "Multiple ▶ RVPI", "value": rvpi, "is_multiple": True},
        {"label": "P&L ▶ Net", "value": net_earnings, "unit": " €"},
        ...
    ]
    """
    with column:
        for spec in specs:
            show_metric(**spec)


# -----------------------------------------------------------------------------
# 4) Advanced equity breakdown helper
# -----------------------------------------------------------------------------

def _display_advanced_portfolio_details() -> None:  # noqa: D401
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

    # Equity ------------------------------------------------------------
    specs1 = [
        {"label": "Equity ▶ Total", "value": balance_summary["total_equity"], "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "normal"},
        {"label": "Equity ▶ Free", "value": balance_summary["total_free_value"], "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "normal"},
        {"label": "Equity ▶ Frozen", "value": balance_summary["total_frozen_value"], "unit": cash_asset, "incomplete": mismatch["total_frozen_value"], "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "Equity ▶ Frozen [Order book]", "value": orders_summary["total_frozen_value"], "unit": cash_asset, "incomplete": mismatch["total_frozen_value"], "delta_fmt": "raw", "delta_color_rule": "off", "incomplete_display": True}
    ]
    # Cash --------------------------------------------------------------
    specs2 = [
        {"label": "Cash ▶ Total", "value": balance_summary["cash_total_value"], "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "Cash ▶ Free", "value": balance_summary["cash_free_value"], "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "Cash ▶ Frozen", "value": balance_summary["cash_frozen_value"], "unit": cash_asset, "incomplete": mismatch["cash_frozen_value"], "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "Cash ▶ Frozen [Order book]", "value": orders_summary["cash_frozen_value"], "unit": cash_asset, "incomplete": mismatch["cash_frozen_value"], "delta_fmt": "raw", "delta_color_rule": "off", "incomplete_display": True}
    ]
    # Assets ------------------------------------------------------------
    specs3 = [
        {"label": "Assets Value ▶ Total", "value": balance_summary["assets_total_value"], "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "Assets Value ▶ Free", "value": balance_summary["assets_free_value"], "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "Assets Value ▶ Frozen", "value": balance_summary["assets_frozen_value"], "unit": cash_asset, "incomplete": mismatch["assets_frozen_value"], "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "Assets Value ▶ Frozen [Order book]", "value": orders_summary["assets_frozen_value"], "unit": cash_asset, "incomplete": mismatch["assets_frozen_value"], "delta_fmt": "raw", "delta_color_rule": "off", "incomplete_display": True}
    ]


    show_metrics_bulk(c1, specs1)
    show_metrics_bulk(c2, specs2)
    show_metrics_bulk(c3, specs3)

    st.markdown("---")

# -----------------------------------------------------------------------------
# 5) Trades summary helpers - Basic
# -----------------------------------------------------------------------------

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
    rvpi_gross = assets_current_value / total_investment if total_investment else None # RVPI = Residual Value to Paid-In
    dpi_gross  = total_divestment / total_investment if total_investment else None # DPI = Distributions to Paid-In
    moic_gross = dpi_gross + rvpi_gross if None not in (dpi_gross, rvpi_gross) else None # MOIC = Multiple on Invested Capital

    # Total trades ------------------------------------------------------------
    # ------------------------------------------------------------------
    # Render three metric columns
    # ------------------------------------------------------------------
    c1, c2, c3 = st.columns(3)

    # Column 1 - Cash & P&L figures -----------------------------------------
    specs1 = [
        {"label": "Market Value ▶ Open Positions", "value": market_value_open, "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "P&L ▶ Net (After Fees)", "value": net_earnings, "unit": cash_asset, "incomplete": incomplete_data, "delta_fmt": "raw", "delta_color_rule": "normal"},
        {"label": "P&L ▶ Gross (Before Fees)", "value": gross_earnings, "unit": cash_asset, "incomplete": incomplete_data, "delta_fmt": "raw", "delta_color_rule": "normal"},
    ]
    # Column 2 - ROI on current risk -----------------------------------------

    if actual_investment > 0:
        specs2 = [
            {"label": "Capital ▶ At Risk (Cost)", "value": actual_investment, "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"},
            {"label": "ROI ▶ Net on Cost", "value": net_roi_on_cost, "value_type": "percent", "delta_fmt": "raw", "incomplete": incomplete_data, "delta_color_rule": "normal"},
            {"label": "ROI ▶ Gross on Cost", "value": gross_roi_on_cost, "value_type": "percent", "delta_fmt": "raw", "incomplete": incomplete_data, "delta_color_rule": "normal"},
        ]
    elif assets_current_value > 0:
        free_carry_surplus = abs(actual_investment)
        specs2 = [
            {"label": "Capital ▶ Free Carry Surplus", "value": free_carry_surplus, "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "normal"},
            {"label": "ROI ▶ Net on Value", "value": net_roi_on_value, "value_type": "percent", "delta_fmt": "raw", "incomplete": incomplete_data, "delta_color_rule": "normal"},
            {"label": "ROI ▶ Gross on Value", "value": gross_roi_on_value, "value_type": "percent", "delta_fmt": "raw", "incomplete": incomplete_data, "delta_color_rule": "normal"},
        ]
    else:
        specs2 = []
    # Column 3 - Multiples as % returns -----------------------------------------
    specs3 = [
        {"label": "Multiple ▶ RVPI (Residual Value to Paid-In)", "value": rvpi_gross, "value_type": "percent", "delta_fmt": "raw", "incomplete": incomplete_data, "delta_color_rule": "off"},
        {"label": "Multiple ▶ DPI (Distributions to Paid-In)", "value": dpi_gross, "value_type": "percent", "delta_fmt": "raw", "incomplete": incomplete_data, "delta_color_rule": "off"},
        {"label": "Multiple ▶ MOIC (Multiple on Invested Capital)", "value": moic_gross, "value_type": "percent", "delta_fmt": "raw", "incomplete": incomplete_data, "delta_color_rule": "normal"}
    ]

    show_metrics_bulk(c1, specs1)
    show_metrics_bulk(c2, specs2)
    show_metrics_bulk(c3, specs3)

# -----------------------------------------------------------------------------
# 6) Trades summary helpers - Advanced
# -----------------------------------------------------------------------------

def _display_advanced_trades_details(trades_summary: dict, cash_asset:str) -> None:  # noqa: D401
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

    specs1 = [
        {"label": "GLOBAL ▶ Notional Traded", "value": total_traded, "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "GLOBAL ▶ Orders Count", "value": total_orders, "delta_fmt": "raw", "delta_color_rule": "off", "value_type": "integer"},
        {"label": "GLOBAL ▶ Avg. Order Size", "value": avg_trade_price_order, "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "GLOBAL ▶ Paid Fees", "value": trades_summary["TOTAL"]["fee"], "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"}
    ]
    specs2 = [
        {"label": "BUY ▶ Notional Invested", "value": total_investment, "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "BUY ▶ Orders Count", "value": count_buy_orders, "delta_fmt": "raw", "delta_color_rule": "off", "value_type": "integer"},
        {"label": "BUY ▶ Avg. Order Size", "value": avg_buy_price_order, "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "BUY ▶ Paid Fees", "value": trades_summary["BUY"]["fee"], "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"}
    ]
    specs3 = [
        {"label": "SELL ▶ Notional Divested", "value": total_divestment, "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "SELL ▶ Orders Count", "value": count_sell_orders, "delta_fmt": "raw", "delta_color_rule": "off", "value_type": "integer"},
        {"label": "SELL ▶ Avg. Order Size", "value": avg_sell_price_order, "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"},
        {"label": "SELL ▶ Paid Fees", "value": trades_summary["SELL"]["fee"], "unit": cash_asset, "delta_fmt": "raw", "delta_color_rule": "off"}
    ]

    show_metrics_bulk(c1, specs1)
    show_metrics_bulk(c2, specs2)
    show_metrics_bulk(c3, specs3)
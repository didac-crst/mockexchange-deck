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
import pandas as pd
import streamlit as st

# Project ---------------------------------------------------------------------
from app.services.api import get_assets_overview

# -----------------------------------------------------------------------------
# 1) Formatting helpers
# -----------------------------------------------------------------------------

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

# -----------------------------------------------------------------------------
# 3) Advanced equity breakdown helper
# -----------------------------------------------------------------------------

def _display_advanced_details() -> None:  # noqa: D401
    """Show an advanced *equity vs frozen* breakdown in three metric columns.

    Fetches the combined summary from ``/overview/assets`` (via
    ``get_assets_overview``), then prints a grid of **st.metric** widgets
    comparing *portfolio* vs *order-book* numbers.  Any mismatch is
    flagged with a warning icon (⚠️) in front of the figure.
    """

    _W = "⚠️"  # warning icon – reused inline for brevity

    summary = get_assets_overview()
    misc = summary.get("misc", {})
    cash_asset = misc.get("cash_asset", "")
    mismatch = misc.get("mismatch", {})  # dict[field -> bool]

    # Local lambdas for consistent formatting ---------------------------
    fmt_cash = lambda v: f"{v:,.2f} {cash_asset}"  # noqa: E731
    fmt = (
        lambda txt, m: f"{_W} {fmt_cash(txt)}" if m else fmt_cash(txt)
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
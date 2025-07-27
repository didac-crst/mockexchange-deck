# _helpers.py

import pandas as pd
import streamlit as st

from app.services.api import get_assets_overview


def _remove_small_zeros(num_str: str) -> str:
    """A number on a string, formatted to 6 decimal places.
    is parsed and the 0 on the right are removed until the units position.
    """
    try:
        # Parse the string as a float and format it
        return num_str.rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return num_str


def _add_details_column(
        df: pd.DataFrame,
        base_url: str,
        *,
        order_id_col: str = "id",
        new_col: str = "Details",
        path_template: str = "?order_id={oid}&page=Orders",
        text = "🔍"
    ) -> pd.DataFrame:
    """
    Return a copy of `df` with a new column `new_col` whose values are
    HTML links pointing at this order’s history.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame must contain a column `order_id_col`.
    base_url : str
        e.g. "http://localhost:8000"
    order_id_col : str
        Name of the column holding the Order ID strings.
    new_col : str
        Name for the new HTML-link column (default: "History").
    path_template : str
        A format string where "{oid}" is interpolated from the order ID.
    link_text : str
        The anchor text for the link (default: a small chain icon).

    Returns
    -------
    pd.DataFrame
        A fresh copy of `df` with `new_col` appended, containing raw
        `<a href=…>` strings.
    """
    df = df.copy()
    # use a *relative* link → stays in the same tab
    def make_url(oid: str) -> str:
        return path_template.format(oid=oid)        #  e.g.  "?order_id=123&page=Orders"
    if not df.empty:
        df[new_col] = df[order_id_col].astype(str).map(make_url)
    return df


def _display_advanced_details() -> None:
    _W = "⚠️"
    summary = get_assets_overview()
    misc = summary.get("misc", {})
    cash_asset = misc.get("cash_asset", "")
    mismatch = misc.get("mismatch", {})
    fmt_cash = lambda v: f"{v:,.2f} {cash_asset}"
    fmt = lambda txt, m: f"{_W} {fmt_cash(txt)}" if m else fmt_cash(txt) # Add warning icon if mismatch
    balance_summary = summary.get("balance_source", {})
    orders_summary = summary.get("orders_source", {})
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Portfolio ▶ Total equity", fmt(balance_summary['total_equity'], False))
        st.metric("Portfolio ▶ Free equity", fmt(balance_summary["total_free_value"], False))
        st.metric("Portfolio ▶ Frozen equity", fmt(balance_summary["total_frozen_value"], mismatch['total_frozen_value']))
        st.metric("Order book ▶ Frozen equity", fmt(orders_summary["total_frozen_value"], mismatch['total_frozen_value']))
    with c2:
        st.metric("Portfolio ▶ Total cash", fmt(balance_summary["cash_total_value"], False))
        st.metric("Portfolio ▶ Free cash", fmt(balance_summary["cash_free_value"], False))
        st.metric("Portfolio ▶ Frozen cash", fmt(balance_summary["cash_frozen_value"], mismatch['cash_frozen_value']))
        st.metric("Order book ▶ Frozen cash", fmt(orders_summary["cash_frozen_value"], mismatch['cash_frozen_value']))
    with c3:
        st.metric("Portfolio ▶ Total assets value", fmt(balance_summary["assets_total_value"], False))
        st.metric("Portfolio ▶ Free assets value", fmt(balance_summary["assets_free_value"], False))
        st.metric("Portfolio ▶ Frozen assets value", fmt(balance_summary["assets_frozen_value"], mismatch['assets_frozen_value']))
        st.metric("Order book ▶ Frozen assets value", fmt(orders_summary["assets_frozen_value"], mismatch['assets_frozen_value']))
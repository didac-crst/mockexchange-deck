# orders.py

import pandas as pd
import streamlit as st
import time, os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

from app.services.api import get_orders
from ._helpers import _remove_small_zeros, _add_details_column
from ._row_colors import _row_style

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ────────────────────────────────────────────────────────────────────────
# Constants & one-off helpers
# ────────────────────────────────────────────────────────────────────────
FRESH_WINDOW_S = int(os.getenv("FRESH_WINDOW_S", 300))  # 5 minutes
N_VISUAL_DEGRADATIONS = int(os.getenv("N_VISUAL_DEGRADATIONS", 12))
SLIDER_MIN = int(os.getenv("SLIDER_MIN", 10))
SLIDER_MAX = int(os.getenv("SLIDER_MAX", 1000))
SLIDER_STEP = int(os.getenv("SLIDER_STEP", 10))
SLIDER_DEFAULT = int(os.getenv("SLIDER_DEFAULT", 100))

def _human_ts(ms: int | None) -> str:
    """
    Convert epoch-milliseconds from the backend into a *local* ISO-like
    time-stamp (``YYYY-MM-DD HH:MM:SS``).  Empty string for nulls so the
    dataframe cell stays blank.
    """
    if ms is None:
        return ""
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ────────────────────────────────────────────────────────────────────────
# Main page renderer
# ────────────────────────────────────────────────────────────────────────
def render() -> None:
    """
    Orders page:

    * Pull the *tail* of the order book from the REST API.
    * Let the user filter by **status / side / type / asset**.
    * Display the table with Streamlit’s dataframe component.
    * Highlight rows that changed in the **last 60 s** to draw attention.
    """
    # params = st.query_params
    # _page = params.get("page", None) # Override if provided
    # if _page:
    #     del st.query_params["page"]

    st.set_page_config(page_title="Orders")
    st.title("Orders")

    # Keys we store in st.session_state for filter persistence
    FILTER_KEYS = ["status_filter", "side_filter", "type_filter", "asset_filter"]

    # ── 1 · Global “Filters” expander ───────────────────────────────────
    filters_expander = st.expander("Filters", expanded=False)
    with filters_expander:
        # Toggle ON to unlimit the number of orders fetched
        limit_toggle = st.checkbox("Fetch the whole order book", value=False, key="limit_toggle")

        if limit_toggle:
            tail = None  # fetch everything
        else:
            tail = st.slider(
                "Max number of last orders to load",
                min_value=SLIDER_MIN,
                max_value=SLIDER_MAX,
                value=SLIDER_DEFAULT,
                step=SLIDER_STEP,
                key="tail_slider",
            )

    # ── 2 · Fetch & massage raw data ────────────────────────────────────
    # if tail is None, get_orders should fetch all orders

    # new: pick up your base‐URL from env (or default)
    base = os.getenv("UI_URL", "http://localhost:8000")
    df_raw = get_orders(tail=tail).pipe(_add_details_column, base_url=base)
    if df_raw.empty:
        st.info("No orders found.")
        return

    df_copy = df_raw.copy()
    df_copy["Posted"]  = df_copy["ts_create"].map(_human_ts)
    df_copy["Updated"] = df_copy["ts_update"].map(_human_ts)
    df_copy[["Asset", "quote_asset"]] = df_copy["symbol"].str.split("/", expand=True)

    # ── 3 · Prepare filter options & maintain session state ─────────────
    def _sync_filter_state(key: str, options: list[str]) -> None:
        """
        Ensure *key* exists in session_state *and* contains only valid choices.
        Keeps the list unchanged if the user cleared everything manually.
        """
        if key not in st.session_state:
            st.session_state[key] = options[:]   # first visit → pre-select all
            return
        # Drop choices that vanished due to data refresh
        st.session_state[key] = [v for v in st.session_state[key] if v in options]

    status_opts = sorted(df_copy["status"].str.replace("_", " ").str.capitalize().unique())
    side_opts   = sorted(df_copy["side"].str.upper().unique())
    type_opts   = sorted(df_copy["type"].str.capitalize().unique())
    asset_opts  = sorted(df_copy["Asset"].unique())

    # Reset filters when ‘tail’ slider jumps to a very different value
    if st.session_state.get("_last_tail") != tail:
        for k in FILTER_KEYS:
            st.session_state.pop(k, None)
        st.session_state["_last_tail"] = tail

    # Keep all filter states in sync with the current option universe
    _sync_filter_state("status_filter", status_opts)
    _sync_filter_state("side_filter",   side_opts)
    _sync_filter_state("type_filter",   type_opts)
    _sync_filter_state("asset_filter",  asset_opts)

    # ── 4 · Render the filter widgets themselves ────────────────────────
    with filters_expander:
        left, right = st.columns([0.8, 0.2])

        with right:
            # Simple “factory-reset” button
            st.write("")  # visual spacer
            if st.button("🔄 Reset filters"):
                for k in FILTER_KEYS:
                    st.session_state.pop(k, None)
                # seed defaults again
                _sync_filter_state("status_filter", status_opts)
                _sync_filter_state("side_filter",   side_opts)
                _sync_filter_state("type_filter",   type_opts)
                _sync_filter_state("asset_filter",  asset_opts)
                st.rerun()

        with left:
            status_sel = st.multiselect("Status", status_opts, key="status_filter")
            side_sel   = st.multiselect("Side",   side_opts,   key="side_filter")
            type_sel   = st.multiselect("Type",   type_opts,   key="type_filter")
            asset_sel  = st.multiselect("Asset (base)", asset_opts, key="asset_filter")

    # ── 5 · Apply filter mask ───────────────────────────────────────────
    mask = (
        df_copy["status"].str.replace("_", " ").str.capitalize().isin(status_sel)
        & df_copy["side"].str.upper().isin(side_sel)
        & df_copy["type"].str.capitalize().isin(type_sel)
        & df_copy["Asset"].isin(asset_sel)
    )
    df = df_copy[mask].copy()
    # Caption with the number of rows loaded
    # and how many are shown in the table
    if tail is not None:
        st.caption(f"🧾 Loaded {len(df_raw)} rows (showing {len(df)}) "
                f"from last {tail} orders")
    else:
        st.caption(f"🧾 Loaded {len(df_raw)} rows (showing {len(df)}) "
                f"from the whole order book")

    # ── 6 · Derive human-readable / numeric helper columns ──────────────
    ts_create_num = pd.to_numeric(df["ts_create"], errors="coerce")
    ts_finish_num = pd.to_numeric(df["ts_finish"], errors="coerce")

    df["Exec. latency"] = (
        (ts_finish_num - ts_create_num).div(1000).round(2).where(ts_finish_num.notna(), "")
    )

    df["Req. Qty"]   = df["amount"].map(lambda v: _remove_small_zeros(f"{v:,.6f}"))
    df["Filled Qty"] = df["actual_filled"].apply(
        lambda v: _remove_small_zeros(f"{v:,.6f}") if pd.notna(v) else ""
    )

    # price / fee / notional prettifiers
    df["Limit price"] = df.apply(
        lambda r: f"{_remove_small_zeros(f'{r.limit_price:,.6f}')}"
                  f" {r.quote_asset}" if pd.notna(r.limit_price) else "",
        axis=1,
    )
    df["Exec. price"] = df.apply(
        lambda r: f"{_remove_small_zeros(f'{r.price:,.6f}')}"
                  f" {r.quote_asset}" if pd.notna(r.price) else "",
        axis=1,
    )

    df["Reserved notional"] = df.apply(
        lambda r: f"{r.reserved_notion_left:,.2f} {r.notion_currency}"
                  if pd.notna(r.reserved_notion_left) else "",
        axis=1,
    )
    df["Actual notional"] = df.apply(
        lambda r: f"{r.actual_notion:,.2f} {r.notion_currency}"
                  if pd.notna(r.actual_notion) else "",
        axis=1,
    )
    df["Reserved fee"] = df.apply(
        lambda r: f"{r.reserved_fee_left:,.2f} {r.fee_currency}"
                  if pd.notna(r.reserved_fee_left) else "",
        axis=1,
    )
    df["Actual fee"] = df.apply(
        lambda r: f"{r.actual_fee:,.2f} {r.fee_currency}"
                  if pd.notna(r.actual_fee) else "",
        axis=1,
    )

    df["Order ID"]      = df["id"].astype(str)
    df["Exec. latency"] = df["Exec. latency"].apply(
        lambda v: f"{v:,.2f} s" if isinstance(v, (int, float)) else ""
    )
    df["Side"]   = df["side"].str.upper()
    df["Type"]   = df["type"].str.capitalize()
    df["Status"] = df["status"].str.replace("_", " ").str.capitalize()

    df_view = df[
        ["Order ID", "Posted", "Updated", "Asset", "Side", "Status", "Type",
         "Limit price", "Exec. price", "Req. Qty", "Filled Qty",
         "Reserved notional", "Actual notional",
         "Reserved fee", "Actual fee", "Exec. latency", "Details"]
    ].sort_values("Updated", ascending=False).reset_index(drop=True)

    # # ── 6½ · Row-level highlighting for *fresh* updates ─────────────────
    styler = (
        df_view.style
            .format({"Details": lambda html: html}, escape="html")
            .apply(_row_style,
                   axis=1,
                   levels=N_VISUAL_DEGRADATIONS,
                   fresh_window_s=FRESH_WINDOW_S)
    )

    # ── 7 · Show the table ──────────────────────────────────────────────

    st.dataframe(
        styler,
        hide_index=True,
        use_container_width=True,
        height=800,   # ~25 rows on FHD
        column_config={
            "Order ID":          st.column_config.TextColumn("Order ID"),
            "Asset":             st.column_config.TextColumn("Asset"),
            "Side":              st.column_config.TextColumn("Side"),
            "Type":              st.column_config.TextColumn("Type"),
            "Status":            st.column_config.TextColumn("Status"),
            "Posted":            st.column_config.DatetimeColumn("Posted",
                                                                format="YY-MM-DD HH:mm:ss"),
            "Updated":           st.column_config.DatetimeColumn("Updated",
                                                                format="YY-MM-DD HH:mm:ss"),
            "Req. Qty":          st.column_config.TextColumn("Req. Qty"),
            "Limit price":       st.column_config.TextColumn("Limit price"),
            "Reserved notional": st.column_config.TextColumn("Reserved notional"),
            "Reserved fee":      st.column_config.TextColumn("Reserved fee"),
            "Filled Qty":        st.column_config.TextColumn("Filled Qty"),
            "Actual notional":   st.column_config.TextColumn("Actual notional"),
            "Actual fee":        st.column_config.TextColumn("Actual fee"),
            "Exec. price":       st.column_config.TextColumn("Exec. price"),
            "Exec. latency":     st.column_config.TextColumn("Exec. latency"),
            # render the URL as a clickable link
            "Details": st.column_config.LinkColumn(
                label="Details",
                display_text="🔍",    # fixed magnifier emoji
                max_chars=1,          # don’t truncate your emoji!
                help="View order details",
            ),
        },
    )
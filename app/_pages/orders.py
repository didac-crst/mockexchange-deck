import os
import time
import pandas as pd
import streamlit as st
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

from app.services.api import get_orders
from ._helpers import _remove_small_zeros
from ._row_colors import _row_style

# Load environment vars
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ────────────────────────────────────────────────────────────────────────
# Configuration constants
# ────────────────────────────────────────────────────────────────────────
FRESH_WINDOW_S = int(os.getenv("FRESH_WINDOW_S", 300))
N_VISUAL_DEGRADATIONS = int(os.getenv("N_VISUAL_DEGRADATIONS", 12))
SLIDER_MIN = int(os.getenv("SLIDER_MIN", 10))
SLIDER_MAX = int(os.getenv("SLIDER_MAX", 1000))
SLIDER_STEP = int(os.getenv("SLIDER_STEP", 10))
SLIDER_DEFAULT = int(os.getenv("SLIDER_DEFAULT", 100))

# ────────────────────────────────────────────────────────────────────────
# Timestamp formatting helper
# ────────────────────────────────────────────────────────────────────────
def _human_ts(ms: int | None) -> str:
    if ms is None:
        return ""
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# ────────────────────────────────────────────────────────────────────────
# Main page renderer
# ────────────────────────────────────────────────────────────────────────
def render() -> None:
    st.set_page_config(page_title="Orders")
    st.title("Orders")

    # Persisted filter keys
    FILTER_KEYS = ["status_filter", "side_filter", "type_filter", "asset_filter"]

    # 1 · Filters expander
    filters_expander = st.expander("Filters", expanded=False)
    with filters_expander:
        # toggle to fetch all
        fetch_all = st.checkbox("Fetch the whole order book", value=False, key="limit_toggle")
        if fetch_all:
            tail = None
        else:
            tail = st.slider(
                "Max number of last orders to load",
                min_value=SLIDER_MIN, max_value=SLIDER_MAX,
                value=SLIDER_DEFAULT, step=SLIDER_STEP,
                key="tail_slider"
            )

    # 2 · Fetch data
    df_raw = get_orders(tail=tail)
    if df_raw.empty:
        st.info("No orders found.")
        return
    df_copy = df_raw.copy()
    df_copy["Posted"] = df_copy["ts_create"].map(_human_ts)
    df_copy["Updated"] = df_copy["ts_update"].map(_human_ts)
    df_copy[["Asset","quote_asset"]] = df_copy["symbol"].str.split("/", expand=True)

    # 3 · Sync filter options
    def _sync_filter_state(key: str, options: list[str]) -> None:
        if key not in st.session_state:
            st.session_state[key] = options[:]
            return
        st.session_state[key] = [v for v in st.session_state[key] if v in options]

    status_opts = sorted(df_copy["status"].str.replace("_"," ").str.capitalize().unique())
    side_opts   = sorted(df_copy["side"].str.upper().unique())
    type_opts   = sorted(df_copy["type"].str.capitalize().unique())
    asset_opts  = sorted(df_copy["Asset"].unique())

    if st.session_state.get("_last_tail") != tail:
        for k in FILTER_KEYS:
            st.session_state.pop(k, None)
        st.session_state["_last_tail"] = tail

    for key, opts in zip(FILTER_KEYS,[status_opts,side_opts,type_opts,asset_opts]):
        _sync_filter_state(key, opts)

    # 4 · Filter widgets
    with filters_expander:
        left,right = st.columns([0.8,0.2])
        with right:
            if st.button("🔄 Reset filters"):
                for k in FILTER_KEYS:
                    st.session_state.pop(k,None)
                for key, opts in zip(FILTER_KEYS,[status_opts,side_opts,type_opts,asset_opts]):
                    _sync_filter_state(key, opts)
                st.rerun()
        with left:
            status_sel = st.multiselect("Status", status_opts, key="status_filter")
            side_sel   = st.multiselect("Side",   side_opts,   key="side_filter")
            type_sel   = st.multiselect("Type",   type_opts,   key="type_filter")
            asset_sel  = st.multiselect("Asset (base)", asset_opts, key="asset_filter")

    # 5 · Apply mask
    mask = (
        df_copy["status"].str.replace("_"," ").str.capitalize().isin(status_sel)
        & df_copy["side"].str.upper().isin(side_sel)
        & df_copy["type"].str.capitalize().isin(type_sel)
        & df_copy["Asset"].isin(asset_sel)
    )
    df = df_copy[mask].copy()

    # caption
    if tail is None:
        st.caption(f"🧾 Loaded {len(df_raw)} rows (showing {len(df)}) from the whole order book")
    else:
        st.caption(f"🧾 Loaded {len(df_raw)} rows (showing {len(df)}) from last {tail} orders")

    # 6 · Prep helper cols
    ts_c = pd.to_numeric(df["ts_create"], errors="coerce")
    ts_f = pd.to_numeric(df["ts_finish"].fillna(0), errors="coerce")
    df["Exec. latency"] = ((ts_f-ts_c).div(1000).round(2).where(ts_f>0, ""))
    df["Req. Qty"]   = df["amount"].map(lambda v: _remove_small_zeros(f"{v:,.6f}"))
    df["Filled Qty"] = df["actual_filled"].apply(lambda v: _remove_small_zeros(f"{v:,.6f}") if pd.notna(v) else "")
    df["Limit price"] = df.apply(lambda r: f"{_remove_small_zeros(f'{r.limit_price:,.6f}')} {r.quote_asset}" if pd.notna(r.limit_price) else "", axis=1)
    df["Exec. price"] = df.apply(lambda r: f"{_remove_small_zeros(f'{r.price:,.6f}')} {r.quote_asset}" if pd.notna(r.price) else "", axis=1)
    df["Reserved notional"] = df.apply(lambda r: f"{r.reserved_notion_left:,.2f} {r.notion_currency}" if pd.notna(r.reserved_notion_left) else "",axis=1)
    df["Actual notional"]  = df.apply(lambda r: f"{r.actual_notion:,.2f} {r.notion_currency}" if pd.notna(r.actual_notion) else "",axis=1)
    df["Reserved fee"] = df.apply(lambda r: f"{r.reserved_fee_left:,.2f} {r.fee_currency}" if pd.notna(r.reserved_fee_left) else "",axis=1)
    df["Actual fee"]   = df.apply(lambda r: f"{r.actual_fee:,.2f} {r.fee_currency}" if pd.notna(r.actual_fee) else "",axis=1)
    df["Order ID"]    = df["id"].astype(str)
    df["Exec. latency"] = df["Exec. latency"].apply(lambda v: f"{v:,.2f} s" if isinstance(v,(int,float)) else "")
    df["Side"]   = df["side"].str.upper()
    df["Type"]   = df["type"].str.capitalize()
    df["Status"] = df["status"].str.replace("_"," ").str.capitalize()

    # final view
    df_view = df[["Order ID","Posted","Updated","Asset","Side","Status","Type",
                   "Limit price","Exec. price","Req. Qty","Filled Qty",
                   "Reserved notional","Actual notional",
                   "Reserved fee","Actual fee","Exec. latency"]]
    df_view = df_view.sort_values("Updated",ascending=False).reset_index(drop=True)

    # 6½ · AgGrid interactive table with a Details button
    builder = GridOptionsBuilder.from_dataframe(df_view)
    # add a blank column for the button
    df_view["Details"] = ""
    js_renderer = JsCode(
        """
class BtnCellRenderer {
  init(params) {
    this.eGui = document.createElement('button');
    this.eGui.innerText = '🔍';
    this.eGui.addEventListener('click', () => {
      window.streamlit.setComponentValue(params.data['Order ID']);
    });
  }
  getGui() { return this.eGui; }
}
"""
    )
    builder.configure_column("Details", cellRenderer=js_renderer, headerName="History", width=90)
    grid_opts = builder.build()

    selected = AgGrid(
        df_view,
        gridOptions=grid_opts,
        allow_unsafe_jscode=True,
        update_mode="NO_UPDATE",
        fit_columns_on_grid_load=True
    ).selected_rows

    # 7 · If row clicked, show history
    if selected:
        oid = selected[0]['Order ID']
        hist = get_orders(tail=None).query(f"id == '{oid}'")["history"].iloc[0]
        with st.expander(f"🔍 History for {oid}", expanded=True):
            st.json(hist)

    # 8 · Finally render the styled DataFrame behind AgGrid fallback
    #    (AgGrid covers the full UX)

    # # ── 6½ · Row-level highlighting for *fresh* updates ─────────────────
    styler = (
        df_view.style
            .apply(
                _row_style,
                axis=1,
                levels=N_VISUAL_DEGRADATIONS,
                fresh_window_s=FRESH_WINDOW_S,
            )
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
        },
    )
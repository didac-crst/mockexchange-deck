import pandas as pd
import streamlit as st
import time
from datetime import datetime, timezone

from app.services.api import get_orders
from ._helpers import _remove_small_zeros


# ────────────────────────────────────────────────────────────────────────
# Constants & one-off helpers
# ────────────────────────────────────────────────────────────────────────
FRESH_WINDOW_S = 60  # seconds
SLIDER_MIN = 10
SLIDER_MAX = 5000
SLIDER_STEP = 10
SLIDER_DEFAULT = 100

_BG = {
    # Status → pastel background for recently-changed rows
    "new":                 "#0073ff",  # blue
    "partially_filled":    "#ffcc00",  # yellow
    "filled":              "#00cc00",  # green
    "canceled":            "#ff4040",  # red
    "partially_canceled":  "#ff4040",
    "rejected":            "#ff4040",
    "expired":             "#ff4040",
}


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
    st.set_page_config(page_title="Orders")
    st.title("Orders")

    # Keys we store in st.session_state for filter persistence
    FILTER_KEYS = ["status_filter", "side_filter", "type_filter", "asset_filter"]

    # ── 1 · Global “Filters” expander ───────────────────────────────────
    filters_expander = st.expander("Filters", expanded=False)
    with filters_expander:
        # Number of most-recent orders to fetch before *any* other widget
        tail = st.slider("Max number of last orders to load",
                         min_value=SLIDER_MIN, max_value=SLIDER_MAX, value=SLIDER_DEFAULT, step=SLIDER_STEP,
                         key="tail_slider")

    # ── 2 · Fetch & massage raw data ────────────────────────────────────
    df_raw = get_orders(tail=tail)
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

    st.caption(f"🧾 Loaded {len(df_raw)} rows (showing {len(df)}) "
               f"from last {tail} orders")

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
         "Reserved fee", "Actual fee", "Exec. latency"]
    ].sort_values("Updated", ascending=False).reset_index(drop=True)

    # ── 6½ · Row-level highlighting for *fresh* updates ─────────────────
    def _row_style(row: pd.Series, *, fresh_window_s: int = FRESH_WINDOW_S) -> list[str]:
        """
        Style callback for ``DataFrame.style.apply``

        If **Updated** is within *fresh_window_s* seconds from “now” colour the
        row by its status, otherwise leave it unstyled.
        """
        try:
            t_update = (
                row["Updated"].timestamp()
                if isinstance(row["Updated"], pd.Timestamp)
                else pd.to_datetime(row["Updated"], errors="coerce").timestamp()
            )
        except Exception:
            t_update = None

        if t_update is None or (time.time() - t_update) > fresh_window_s:
            return [""] * len(row)

        bg = _BG.get(str(row["Status"]).lower().replace(" ", "_"), "")
        return [f"background-color:{bg};color:black" if bg else ""] * len(row)

    styler = df_view.style.apply(_row_style, axis=1)
    #   Index left visible – users often want a stable numeric row id

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
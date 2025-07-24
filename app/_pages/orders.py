import pandas as pd
import streamlit as st
from datetime import datetime, timezone
from app.services.api import get_orders

from ._helpers import _remove_small_zeros


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #

def _human_ts(ms: int | None) -> str:
    """Return `YYYY-MM-DD HH:MM:SS` in the user’s local TZ (Europe/Berlin)."""
    if ms is None:
        return ""
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def render() -> None:
    st.set_page_config(page_title="Orders")
    st.title("Orders")

    FILTER_KEYS = ["status_filter", "side_filter", "type_filter", "asset_filter"]

    # ---------- 1 · Filters expander (define once, reuse) -------------------
    filters_expander = st.expander("Filters", expanded=False)

    # 1-a Slider first (needs to run before API call)
    with filters_expander:
        tail = st.slider(
            "Max number of last orders to load",
            10, 5000, 50, 10,
            key="tail_slider",
        )

    # 1-b Fetch data
    df_raw = get_orders(tail=tail)
    if df_raw.empty:
        st.info("No orders found.")
        return

    # ---------- 2 · Data massage -------------------------------------------
    df_copy = df_raw.copy()
    df_copy["Posted"] = df_copy["ts_create"].map(_human_ts)
    df_copy["Updated"] = df_copy["ts_update"].map(_human_ts)
    df_copy[["Asset", "quote_asset"]] = df_copy["symbol"].str.split("/", expand=True)

    # ---------- 3 · Init & sync filter state --------------------------------
    def _sync_filter_state(key: str, options: list[str]) -> None:
        """Ensure session_state[key] exists and only contains valid options.
        If it's empty, keep it empty (user intentionally cleared it)."""
        if key not in st.session_state:
            st.session_state[key] = options[:]          # first init = all
            return

        kept = [v for v in st.session_state[key] if v in options]
        # DO NOT auto-refill if user cleared everything
        st.session_state[key] = kept

    # Build option lists once
    status_opts = df_copy["status"].str.replace("_", " ").str.capitalize().unique().tolist()
    side_opts   = df_copy["side"].str.upper().unique().tolist()
    type_opts   = df_copy["type"].str.capitalize().unique().tolist()
    asset_opts  = df_copy["Asset"].unique().tolist()

    # Optional: reset when tail changed drastically (prevents stale selections)
    if st.session_state.get("_last_tail") != tail:
        for k in FILTER_KEYS:
            st.session_state.pop(k, None)
        st.session_state["_last_tail"] = tail

    # Sync all filters
    _sync_filter_state("status_filter", status_opts)
    _sync_filter_state("side_filter",   side_opts)
    _sync_filter_state("type_filter",   type_opts)
    _sync_filter_state("asset_filter",  asset_opts)

    # ---------- 4 · Widgets (same expander) --------------------------------
    with filters_expander:
        left, right = st.columns([0.8, 0.2])

        with right:
            st.write("")  # spacer
            st.write("")  # (optional) push button down a bit
            if st.button("🔄 Reset filters"):
                for k in FILTER_KEYS:
                    st.session_state.pop(k, None)
                # Re-seed defaults
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

    # ---------- 5 · Apply mask ---------------------------------------------
    mask = (
        df_copy["status"].str.replace("_", " ").str.capitalize().isin(status_sel)
        & df_copy["side"].str.upper().isin(side_sel)
        & df_copy["type"].str.capitalize().isin(type_sel)
        & df_copy["Asset"].isin(asset_sel)
    )
    df = df_copy[mask].copy()

    # ---------- 6 · Rest of your logic (unchanged) --------------------------
    ts_create_num = pd.to_numeric(df["ts_create"], errors="coerce")
    ts_finish_num = pd.to_numeric(df["ts_finish"], errors="coerce")
    ts_update_num = pd.to_numeric(df["ts_update"], errors="coerce")
    df["Exec. latency"] = (
        (ts_finish_num - ts_create_num)
        .div(1000)
        .round(2)
        .where(ts_finish_num.notna(), "")
    )

    df["Req. Qty"]     = df["amount"].apply(lambda v: f"{v:,.6f}").apply(_remove_small_zeros)
    df["Filled Qty"]   = df["actual_filled"].apply(lambda v: f"{v:,.6f}" if pd.notna(v) else "").apply(_remove_small_zeros)

    df["Limit price"] = df.apply(
        lambda r: (
            f"{_remove_small_zeros('{:,.6f}'.format(r['limit_price']))} {r['quote_asset']}"
            if pd.notna(r['limit_price']) else ""
        ),
        axis=1,
    )
    df["Exec. price"] = df.apply(
        lambda r: (
            f"{_remove_small_zeros('{:,.6f}'.format(r['price']))} {r['quote_asset']}"
            if pd.notna(r["price"]) else ""
        ),
        axis=1
    )

    df["Reserved notional"] = df.apply(
        lambda r: f"{r['reserved_notion_left']:,.2f} {r['notion_currency']}" if pd.notna(r["reserved_notion_left"]) else "",
        axis=1
    )
    df["Actual notional"] = df.apply(
        lambda r: f"{r['actual_notion']:,.2f} {r['notion_currency']}" if pd.notna(r["actual_notion"]) else "",
        axis=1,
    )
    df["Reserved fee"] = df.apply(
        lambda r: f"{r['reserved_fee_left']:,.2f} {r['fee_currency']}" if pd.notna(r["reserved_fee_left"]) else "",
        axis=1
    )
    df["Actual fee"] = df.apply(
        lambda r: f"{r['actual_fee']:,.2f} {r['fee_currency']}" if pd.notna(r["actual_fee"]) else "",
        axis=1,
    )

    df["Order ID"] = df["id"].astype(str)
    df["Exec. latency"] = df["Exec. latency"].apply(
        lambda v: f"{v:,.2f} s" if isinstance(v, (int, float)) and pd.notna(v) else ""
    )

    df["Side"]   = df["side"].str.upper()
    df["Type"]   = df["type"].str.capitalize()
    df["Status"] = df["status"].str.replace("_", " ").str.capitalize()

    df_view = df[
        [
            "Posted", "Order ID", "Updated", "Asset", "Side", "Status", "Type", "Limit price",
            "Exec. price", "Req. Qty", "Filled Qty", "Reserved notional", "Actual notional",
            "Reserved fee", "Actual fee", "Exec. latency",
        ]
    ]
    # sort by Posted date, descending
    df_view = df_view.sort_values("Posted", ascending=False)

    # ------------------------------------------------------------------ #
    # 6½ · Row-highlighting for “fresh” updates                          #
    # ------------------------------------------------------------------ #

    # 1) keep helper col for Pandas to read in the styling callback
    df_view["updated_ms"] = df["ts_update"].astype("Int64")

    last_seen = st.session_state.get("orders_last_seen")

    def _row_style(row: pd.Series) -> list[str]:
        """Return CSS strings (one per cell) – pastel bg + black text for *new* rows."""
        if (
            last_seen is None
            or pd.isna(row["updated_ms"])
            or row["updated_ms"] <= last_seen
        ):
            return [""] * len(row)   # unchanged row → no styling

        bg = {
            "new":                 "#cce0ff",  # blue
            "partially_filled":    "#fff4cc",  # yellow
            "filled":              "#d4edda",  # green
            "canceled":            "#f8d7da",  # red-ish
            "partially_canceled":  "#f8d7da",
            "rejected":            "#f8d7da",
            "expired":             "#f8d7da",
        }.get(row["Status"].lower().replace(" ", "_"), "")

        style = f"background-color: {bg}; color: black" if bg else ""
        return [style] * len(row)

    styler = (
        df_view.style
            .apply(_row_style, axis=1)
            .hide(axis="index")                 # hide the numeric index
            .hide(axis="columns", subset=["updated_ms"])   #  <-- tell it “column”
    )

    # ------------------------------------------------------------------ #
    # 7 · Streamlit interactive table                                    #
    # ------------------------------------------------------------------ #
    st.dataframe(
        styler,                     # <-- pass the Styler directly!
        use_container_width=True,
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

    # ------------------------------------------------------------------ #
    # 8 · Remember newest ts_update for next refresh                     #
    # ------------------------------------------------------------------ #
    if not df_view["updated_ms"].isna().all():
        st.session_state["orders_last_seen"] = int(df_view["updated_ms"].max())

    st.caption(
        f"🧾 Loaded {len(df_raw)} rows (showing {len(df_view)}) "
        f"from last {tail} orders"
    )
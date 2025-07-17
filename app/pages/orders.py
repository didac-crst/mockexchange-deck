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

# --------------------------------------------------------------------- #
# Main render function
# --------------------------------------------------------------------- #

def render() -> None:
    # ── 1 · Fetch raw orders ------------------------------------------------
    df_raw = get_orders()                         # raw cols exactly as the API sends

    if df_raw.empty:
        st.info("No orders found.")
        return

    # ── 2 · Data-massage ----------------------------------------------------
    df_copy = df_raw.copy()

    # 2-a  Readable timestamps
    df_copy["Posted"] = df_copy["ts_post"].map(_human_ts)

    # 2-b  Split symbol into base / quote
    df_copy[["Asset", "quote_asset"]] = df_copy["symbol"].str.split("/", expand=True)

    # ── FILTERS ────────────────────────────────────────────────────────── #
    with st.expander("Filters", expanded=False):
        # • Streamlit widgets return Python lists → amenable to .isin()
        status_sel = st.multiselect(
            "Status", df_copy["status"].str.capitalize().unique().tolist(),
            default=df_copy["status"].str.capitalize().unique().tolist()
        )
        side_sel = st.multiselect(
            "Side", df_copy["side"].str.upper().unique().tolist(),
            default=df_copy["side"].str.upper().unique().tolist()
        )
        type_sel = st.multiselect(
            "Type", df_copy["type"].str.capitalize().unique().tolist(),
            default=df_copy["type"].str.capitalize().unique().tolist()
        )
        asset_sel = st.multiselect(
            "Asset (base)", df_copy["Asset"].unique().tolist(),
            default=df_copy["Asset"].unique().tolist()
        )

    # Boolean mask (no copy yet → cheap)
    mask = (
        df_copy["status"].str.capitalize().isin(status_sel)
        & df_copy["side"].str.upper().isin(side_sel)
        & df_copy["type"].str.capitalize().isin(type_sel)
        & df_copy["Asset"].isin(asset_sel)
    )

    df = df_copy[mask].copy()      # operate on the filtered slice from here on
    # ───────────────────────────────────────────────────────────────────── #

    # 2-c  Execution latency in seconds
    ts_post_num  = pd.to_numeric(df["ts_post"], errors="coerce")
    ts_exec_num  = pd.to_numeric(df["ts_exec"], errors="coerce")
    df["Exec latency"] = (
        (ts_exec_num - ts_post_num)            # vectorised diff → float64
        .div(1000)                             # ms → s
        .round(2)
        .where(ts_exec_num.notna(), "")        # blank for open orders
    )

    # 2-d  Quantities
    df["Booked Qty"] = df["amount"].apply(lambda v: f"{v:,.6f}").apply(_remove_small_zeros)
    df["Final Qty"]    = df["filled"].apply(lambda v: f"{v:,.6f}" if pd.notna(v) else "").apply(_remove_small_zeros)

    # 2-e  Limit / exec prices (currency embedded, blank if None)
    df["Limit price"] = df.apply(
        lambda r: (
            f"{_remove_small_zeros('{:,.6f}'.format(r['limit_price']))} {r['quote_asset']}"
            if pd.notna(r['limit_price']) else ""
        ),
        axis=1,
    )
    df["Exec price"] = df.apply(
        lambda r: (
            f"{_remove_small_zeros('{:,.6f}'.format(r['price']))} {r['quote_asset']}"
            if pd.notna(r["price"]) else ""
        ),
        axis=1
    )

    # 2-f  Notions & fees with per-row currencies
    df["Booked notion"] = df.apply(
        lambda r: f"{r['booked_notion']:,.2f} {r['notion_currency']}" if pd.notna(r["booked_notion"]) else "",
        axis=1
    )
    df["Final notion"] = df.apply(
        lambda r: f"{r['notion']:,.2f} {r['notion_currency']}" if pd.notna(r["notion"]) else "",
        axis=1,
    )
    df["Booked fee"] = df.apply(
        lambda r: f"{r['booked_fee']:,.2f} {r['fee_currency']}", axis=1
    )
    df["Final fee"] = df.apply(
        lambda r: f"{r['fee_cost']:,.2f} {r['fee_currency']}" if pd.notna(r["fee_cost"]) else "",
        axis=1,
    )

    # 2-g Other columns
    df["Order ID"] = df["id"].astype(str)  # ensure string type
    # df["Exec latency"] = df.apply(
    #     lambda r: f"{r['Exec latency']:,.2f} s" if pd.notna(r["Exec latency"]) else "",
    #     axis=1
    # )
    df["Exec latency"] = df["Exec latency"].apply(
        lambda v: f"{v:,.2f} s" if isinstance(v, (int, float)) and pd.notna(v) else ""
    )

    # 2-g  Readable enums
    df["Side"]   = df["side"].str.upper()
    df["Type"]   = df["type"].str.capitalize()
    df["Status"] = df["status"].str.capitalize()

    # ── 3 · Keep only the pretty columns, rename nicely ---------------------
    df_view = df[
        [
            "Posted",
            "Order ID",
            "Asset",
            "Side",
            "Type",
            "Status",
            "Booked Qty",
            "Limit price",
            "Booked notion",
            "Booked fee",
            "Final Qty",
            "Exec price",
            "Final notion",
            "Final fee",
            "Exec latency",
        ]
    ]

    st.dataframe(
        df_view,
        hide_index=True,
        column_config={
            "Order ID":  st.column_config.TextColumn("Order ID"),
            "Asset":      st.column_config.TextColumn("Asset"),
            "Side":       st.column_config.TextColumn("Side"),
            "Type":       st.column_config.TextColumn("Type"),
            "Status":     st.column_config.TextColumn("Status"),
            "Posted":     st.column_config.DatetimeColumn("Posted", format="YYYY-MM-DD HH:mm:ss"),
            "Qty Submitted": st.column_config.TextColumn("Qty Submitted"),
            "Limit price": st.column_config.TextColumn("Limit price"),
            "Booked notion": st.column_config.TextColumn("Booked notion"),
            "Booked fee": st.column_config.TextColumn("Booked fee"),
            "Qty Filled": st.column_config.TextColumn("Qty Filled"),
            "Exec price": st.column_config.TextColumn("Exec price"),
            "Final notion": st.column_config.TextColumn("Final notion"),
            "Final fee": st.column_config.TextColumn("Final fee"),
            "Exec latency": st.column_config.TextColumn("Exec latency"),
        },
    )

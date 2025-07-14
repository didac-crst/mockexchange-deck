import pandas as pd
import streamlit as st
from datetime import datetime, timezone
from app.services.api import get_orders


def _human_ts(ms: int | None) -> str:
    """Return `YYYY-MM-DD HH:MM:SS` in the user’s local TZ (Europe/Berlin)."""
    if ms is None:
        return ""
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def render() -> None:
    # ── 1 · Fetch raw orders ------------------------------------------------
    df = get_orders()                         # raw cols exactly as the API sends

    if df.empty:
        st.info("No orders found.")
        return

    # ── 2 · Data-massage ----------------------------------------------------
    df = df.copy()

    # 2-a  Readable timestamps
    df["Posted"] = df["ts_post"].map(_human_ts)

    # 2-b  Split symbol into base / quote
    df[["Asset", "quote_asset"]] = df["symbol"].str.split("/", expand=True)

    # 2-c  Execution latency in seconds
    ts_post_num  = pd.to_numeric(df["ts_post"], errors="coerce")
    ts_exec_num  = pd.to_numeric(df["ts_exec"], errors="coerce")
    df["Exec latency (s)"] = (
        (ts_exec_num - ts_post_num)            # vectorised diff → float64
        .div(1000)                             # ms → s
        .round(2)
        .where(ts_exec_num.notna(), "")        # blank for open orders
    )

    # 2-d  Quantities
    df["Booked Qty"] = df["amount"].apply(lambda v: f"{v:,.6f}")
    df["Final Qty"]    = df["filled"].apply(lambda v: f"{v:,.6f}" if pd.notna(v) else "")

    # 2-e  Limit / exec prices (currency embedded, blank if None)
    df["Limit price"] = df.apply(
        lambda r: f"{r['limit_price']:,.6f} {r['quote_asset']}" if pd.notna(r["limit_price"]) else "",
        axis=1,
    )
    df["Exec price"] = df.apply(
        lambda r: f"{r['price']:,.6f} {r['quote_asset']}" if pd.notna(r["price"]) else "",
        axis=1,
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

    # 2-g  Readable enums
    df["Side"]   = df["side"].str.upper()
    df["Type"]   = df["type"].str.capitalize()
    df["Status"] = df["status"].str.capitalize()

    # ── 3 · Keep only the pretty columns, rename nicely ---------------------
    df_view = df[
        [
            "Posted",
            "id",
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
            "Exec latency (s)",
        ]
    ].rename(
        columns={
            "id": "Order ID",
        }
    )

    # ── 4 · Display ---------------------------------------------------------
    st.markdown(
        """
        <style>
        /* right-align every cell inside this dataframe */
        div[data-testid="stDataFrame"] div[role="gridcell"] {
            justify-content: flex-end !important;
            text-align: right !important;
        }
        /* left-align the first two (ID & Pair) for readability */
        div[data-testid="stDataFrame"] div[role="gridcell"]:nth-child(1),
        div[data-testid="stDataFrame"] div[role="gridcell"]:nth-child(2) {
            justify-content: flex-start !important;
            text-align: left !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

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
            "Exec latency (s)": st.column_config.TextColumn("Exec latency (s)"),
        },
    )

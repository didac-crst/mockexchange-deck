# # app/_pages/order_details.py

# from pathlib import Path
# from dotenv import load_dotenv
# import streamlit as st
# import requests, os

# load_dotenv(Path(__file__).parent.parent.parent / ".env")

# API_BASE = os.getenv("API_BASE", "http://localhost:8000")


# def render(order_id: str) -> None:
#     st.set_page_config(page_title=f"Order {order_id} history")
#     st.header(f"Order #{order_id} – execution history")
#     st.markdown("This page shows the execution history of a specific order.")

#     # Fetch & show
#     url = f"{API_BASE}/orders/{order_id}?include_history=true"
#     try:
#         resp = requests.get(url, timeout=10)
#         resp.raise_for_status()
#         data = resp.json()
#     except Exception as exc:
#         st.error(f"Could not load history:\n```\n{exc}\n```")
#         return

#     if not data:
#         st.info("No history found for this order.")
#         return

#     # One-liner: render whatever shape your endpoint returns
#     st.json(data, expanded=False)

# app/_pages/order_history.py

from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
import requests, os
import pandas as pd
from datetime import datetime, timezone

from ._helpers import _remove_small_zeros
from ._row_colors import _STATUS_LIGHT

load_dotenv(Path(__file__).parent.parent.parent / ".env")
API_BASE = os.getenv("API_BASE", "http://localhost:8000")

def _human_ts(ms: int | None) -> str:
    """Convert epoch‐ms to local YYYY-MM-DD HH:MM:SS, blank on None."""
    if ms is None:
        return ""
    dt = datetime.fromtimestamp(ms/1000, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def render(order_id: str) -> None:

    # Format numbers
    fmt = lambda v: _remove_small_zeros(f"{v:,.6f}")
    fmt_notion = lambda v: f"{v:,.2f} {data.get('notion_currency')}"
    fmt_fee = lambda v: f"{v:,.4f} {data.get('fee_currency')}"

    # ── “Back” button ────────────────────────────────────────────────────────
    if st.button("← Back to Order Book"):
        # Remove the order_id key from the URL query params
        if "order_id" in st.query_params:
            del st.query_params["order_id"]
            # st.query_params["page"] = "Orders"  # Ensure we show the Orders page
        # Re-run so that main.py sees no order_id and shows Orders again
        st.rerun()

    # Fetch from API
    url = f"{API_BASE}/orders/{order_id}?include_history=true"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        st.error(f"Could not load history:\n```\n{exc}\n```")
        return

    data_keys = list(data.keys())
    # If order not found, there is a dict with an "error" key
    if "error" in data_keys:
        st.info("No history found for order ID "
                f"{order_id} - Probably it has been pruned.")
        return

    # ── 0) Prepare data ───────────────────────────────────────────────────
    ticker = data.get("symbol")
    asset = ticker.split("/")[0]
    side = data.get("side").upper()
    _status = data.get("status")
    status_light = _STATUS_LIGHT.get(_status, "⚪")  # default to white circle
    status = _status.replace("_", " ").capitalize()
    type_info = (
        f"{data.get('type').capitalize()} [{fmt(data.get('limit_price',0))} {data.get('notion_currency')}]" if data.get("type") == "limit" else data.get("type").capitalize()
    )
    _price = data.get("price", 0)
    if _price is None or _price == 0:
        price = None
    else:
        price = f"{fmt(data.get('price', 0))} {data.get('notion_currency')}"

    placed_ts  = _human_ts(data.get("ts_create"))
    updated_ts = _human_ts(data.get("ts_update"))
    executed_ts = _human_ts(data.get("ts_finish")) if data.get("ts_finish") else None
    is_finished = executed_ts is not None
    latency = (
        "{:,.2f} seconds".format((data.get("ts_finish") - data.get("ts_create")) / 1000)
        if data.get("ts_finish") else "N/A"
    )

    # ── 1) Overview as metrics ────────────────────────────────────────────
    st.set_page_config(page_title=f"Order {order_id}")
    st.header(f"{status_light} {side} Order #{order_id} [{ticker}]")

    # Layout in three columns of big numbers/text
    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            label="Asset",
            value=asset,
            delta=None,
            delta_color="off",
        )
        st.metric(
            label="Status",
            value=status,
            delta=None,
            delta_color="off",
        )
    with c2:
        st.metric(
            label="Type",
            value=type_info,
            delta=None,
            delta_color="off",
        )
        if price is not None:
            st.metric(
                label="Average price",
                value=price,
                delta=None,
                delta_color="off",
        )
    with c3:
        st.metric(
            label="Created",
            value=placed_ts,
            delta=None,
            delta_color="off",
        )
        st.metric(
            label="Finished" if is_finished else "Updated",
            value=updated_ts,
            delta=None,
            delta_color="off",
        )
        if is_finished:
            st.metric(
                label="Latency",
                value=latency,
                delta=None,
                delta_color="off",
            )
    st.markdown("---")

    # ── Compact summary grid ───────────────────────────────────────────────
    st.subheader("Quick summary")

    # Compute the values
    initial_amount    = data.get("amount", 0)
    filled_amount     = data.get("actual_filled", 0)
    remaining_amount  = initial_amount - filled_amount

    initial_notion    = data.get("initial_booked_notion", 0)
    actual_notion     = data.get("actual_notion", 0)
    remaining_notion  = data.get("reserved_notion_left", 0)

    initial_fee       = data.get("initial_booked_fee", 0)
    actual_fee        = data.get("actual_fee", 0)
    remaining_fee     = data.get("reserved_fee_left", 0)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Asset ▶ Initial requested",  fmt(initial_amount))
        st.metric("Asset ▶ Actual filled",      fmt(filled_amount))
        st.metric("Asset ▶ Missing",            fmt(remaining_amount))

    with col2:
        st.metric("Notional ▶ Initial booked",  fmt_notion(initial_notion))
        actual_str = f"Notional ▶ {'Actual paid' if side == 'BUY' else 'Actual received'}"
        st.metric(actual_str,     fmt_notion(actual_notion))
        st.metric("Notional ▶ Still booked",       fmt_notion(remaining_notion))

    with col3:
        st.metric("Fee ▶ Initial booked",       fmt_fee(initial_fee))
        st.metric("Fee ▶ Actual paid",          fmt_fee(actual_fee))
        st.metric("Fee ▶ Still booked",            fmt_fee(remaining_fee))

    st.markdown("---")

    # ── 2) History table ─────────────────────────────────────────────────
    history = data.get("history", {})
    # Turn nested dict into list of records
    records = []
    for step in sorted(history.keys(), key=int):
        rec = history[step]
        records.append({
            "Step":            int(step),
            "Time":            _human_ts(rec.get("ts")),
            "Status":          rec.get("status").replace("_"," ").capitalize(),
            "Price":           rec.get("price") or "",
            "Actual filled":    rec.get("actual_filled") or "",
            "Remaining":       rec.get("amount_remain"),
            "Actual Notional":   rec.get("actual_notion"),
            "Notional left":     rec.get("reserved_notion_left"),
            "Actual Fee":        rec.get("actual_fee"),
            "Fee left":          rec.get("reserved_fee_left"),
            "Comment":          rec.get("comment", ""),
        })
    df_hist = pd.DataFrame(records)

    st.subheader("Fill history")
    st.dataframe(df_hist, hide_index=True, use_container_width=True)
# app/main.py

import streamlit as st
from streamlit_autorefresh import st_autorefresh

# 1) Wide layout must be set before any other st calls:
st.set_page_config(page_title="MockExchange Dashboard", layout="wide", initial_sidebar_state="expanded")

from app.config import settings
from app._pages import portfolio, orders, order_details

# Sidebar navigation
st.sidebar.title("MockExchange")
default_idx = 1     # 0 → first option, 1 → second, …

# # Grab URL params early
params = st.query_params
oid = params.get("order_id", None)
# _page = params.get("page", None) # Override if provided
# if _page and _page == "Orders":
#     default_idx = 1
#     del st.query_params["page"]  # Remove page param to avoid confusion

page = st.sidebar.radio(
        "Navigate",
        ("Portfolio", "Orders"),
        index=default_idx,          # pre-select “Orders”
        key="sidebar_page",
)

# Auto-refresh every N seconds
st_autorefresh(interval=settings()["REFRESH_SECONDS"] * 1000, key="refresh")

# If an order_id is in the URL, show its details
if oid:
    order_details.render(order_id=oid)

# Otherwise show the selected page
else:
    if page == "Portfolio":
        portfolio.render()
    else:  # page == "Orders"
        orders.render()
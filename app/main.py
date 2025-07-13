import streamlit as st
from streamlit_autorefresh import st_autorefresh
from app.config import settings
from app.pages import dashboard, orders

st.sidebar.title("mockexchange‑deck")
page = st.sidebar.radio("Navigate", ("Dashboard", "Orders"))

st_autorefresh(interval=settings()["REFRESH_SECONDS"] * 1000, key="refresh")

if page == "Dashboard":
    dashboard.render()
else:
    orders.render()
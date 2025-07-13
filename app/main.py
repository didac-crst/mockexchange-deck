import streamlit as st
from streamlit_autorefresh import st_autorefresh
from app.config import settings
from app.pages import orders, portfolio

st.sidebar.title("MockExchange")
page = st.sidebar.radio("Navigate", ("portfolio", "orders"))

st_autorefresh(interval=settings()["REFRESH_SECONDS"] * 1000, key="refresh")

if page == "portfolio":
    portfolio.render()
else:
    orders.render()
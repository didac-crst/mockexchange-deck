import streamlit as st
from streamlit_autorefresh import st_autorefresh
from app.config import settings
from app.pages import orders, portfolio

st.sidebar.title("MockExchange Deck")
page = st.sidebar.radio("Navigate", ("Portfolio", "Orders"))

st_autorefresh(interval=settings()["REFRESH_SECONDS"] * 1000, key="refresh")

if page == "Portfolio":
    portfolio.render()
else:
    orders.render()
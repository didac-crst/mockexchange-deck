import streamlit as st
from app.services.api import get_orders

def render():
    df = get_orders()
    st.dataframe(df)
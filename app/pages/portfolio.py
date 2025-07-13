import pandas as pd
import streamlit as st
import plotly.express as px
import streamlit as st
from app.services.api import get_balance


def render():
    data = get_balance()

    if data["assets_df"].empty:
        st.info("No equity or assets found.")
        return

    # ── 1. Equity metric ────────────────────────────────────────────────────
    equity_str = f"{data['equity']:,.2f} {data['quote_asset']}"
    st.metric("Total equity", equity_str)

    # ── 2 · Build tidy numeric DataFrame ──────────────────────────────────────
    df = data["assets_df"].copy()
    df["value"] = df["total"] * df["quote_price"]

    # share of portfolio as a pure number (0-1); keep it numeric for easy maths
    df["share"] = df["value"] / df["value"].sum()
    df = df.sort_values("value", ascending=False)

    # ── 3 · Pie chart with “Other” bucket -------------------------------------
    lim_min_share = 0.05          # 5 %
    if len(df) <= 10:
        major = df
        other = 0
    else:
        major = df[df["share"] >= lim_min_share]
        other = df.loc[df["share"] < lim_min_share, "value"].sum()

    pie_df = major[["asset", "value"]]
    if other > 0:
        pie_df.loc[len(pie_df)] = {"asset": "Other", "value": other}

    fig = px.pie(pie_df, names="asset", values="value", hole=0.4)
    st.plotly_chart(fig, use_container_width=True)

    # ── 4 · Pretty table (add thousand-sep strings, right-align) --------------
    def fmt_amt(x, dec=6):   return f"{x:,.{dec}f}"
    def fmt_val(x):          return f"{x:,.2f} {data['quote_asset']}"
    def fmt_pct(x):          return f"{x*100:,.2f}%"

    df_disp = df.copy()
    df_disp["free"]        = df["free"].map(fmt_amt)
    df_disp["used"]        = df["used"].map(fmt_amt)
    df_disp["total"]       = df["total"].map(fmt_amt)
    df_disp["quote_price"] = df["quote_price"].map(fmt_amt)
    df_disp["value"]       = df["value"].map(fmt_val)
    df_disp["share"]       = df["share"].map(fmt_pct)

    st.dataframe(
        df_disp,
        hide_index=True,
        column_order=["asset","free","used","total","quote_price","value","share"],
        column_config={
            "asset": st.column_config.TextColumn("Asset"),
            "free":  st.column_config.TextColumn("Free"),
            "used":  st.column_config.TextColumn("In orders"),
            "total": st.column_config.TextColumn("Total"),
            "quote_price": st.column_config.TextColumn(f"Price ({data['quote_asset']})"),
            "value": st.column_config.TextColumn(f"Value ({data['quote_asset']})"),
            "share": st.column_config.TextColumn("Share"),
        },
    )
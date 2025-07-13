import pandas as pd
import streamlit as st
import plotly.express as px
from app.services.api import get_balance


def render():
    data = get_balance()

    # ── 1. Equity metric ────────────────────────────────────────────────────
    equity_str = f"{data['equity']:,.2f} {data['quote_asset']}"
    st.metric("Total equity", equity_str)

    # ── 2. Prep DataFrame with formatting ────────────────────────────────────
    df = data["assets_df"].copy()
    df["value"] = df["total"] * df["quote_price"]
    df = df.sort_values("value", ascending=False)
    df["cum%"] = df["value"].cumsum() / df["value"].sum()

    # # add “Total” row
    # total_row = pd.DataFrame(
    #     {
    #         "asset": ["Total"],
    #         "total": [df["total"].sum()],
    #         "quote_price": [pd.NA],
    #         "value": [df["value"].sum()],
    #         "cum%": [pd.NA],
    #     }
    # )
    # df_disp = pd.concat([df, total_row], ignore_index=True)

    # ---------- a) number formatting ----------------------------------------
    df_fmt = df.copy()
    df_fmt["free"]       = df_fmt["free"].apply(lambda x: f"{x:,}" if pd.notna(x) else "")
    df_fmt["used"]       = df_fmt["used"].apply(lambda x: f"{x:,}" if pd.notna(x) else "")
    df_fmt["total"]       = df_fmt["total"].apply(lambda x: f"{x:,}" if pd.notna(x) else "")
    df_fmt["quote_price"] = df_fmt["quote_price"].apply(lambda x: f"{x:,.6f}" if pd.notna(x) else "")
    df_fmt["value"]       = df_fmt["value"].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "")

    # ---------- b) turn cum% into pretty text, then rename once --------------
    df_fmt["cum%"] = (
        df["cum%"].mul(100)
                    .round(2)
                    .astype(str)
                    .str.rstrip("0")
                    .str.rstrip(".")
                    .add("%")
                    .where(df["cum%"].notna(), "")   # blank for NaNs
    )
    df_fmt = df_fmt.rename(columns={"cum%": "cum"})

    # ── 3. Pie chart (unchanged) ────────────────────────────────────────────
    major   = df[df["cum%"] <= 0.9]
    other   = df[df["cum%"] > 0.9]["value"].sum()
    pie_df  = major[["asset", "value"]]
    if other > 0:
        pie_df.loc[len(pie_df)] = {"asset": "Other", "value": other}

    fig = px.pie(pie_df, names="asset", values="value", hole=0.4)
    st.plotly_chart(fig, use_container_width=True)

    # ── 4. Display the table ────────────────────────────────────────────────
    st.dataframe(df_fmt, hide_index=True)
import streamlit as st, plotly.express as px
from app.services.api import get_balance

def render():
    data = get_balance()
    st.metric("Total equity", f"{data['equity']:.2f} USDT")

    df = data["assets_df"].copy()
    df["value"] = df["total"] * df["quote_price"]  # assumes backend sends quote_price
    df_sort = df.sort_values("value", ascending=False)
    df_sort["cum%"] = df_sort["value"].cumsum() / df_sort["value"].sum()
    major = df_sort[df_sort["cum%"] <= 0.9]
    other_val = df_sort[df_sort["cum%"] > 0.9]["value"].sum()
    pie_df = major[["asset", "value"]]
    if other_val > 0:
        pie_df = pie_df.append({"asset": "Other", "value": other_val}, ignore_index=True)

    fig = px.pie(pie_df, names="asset", values="value", hole=0.4)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df_sort)
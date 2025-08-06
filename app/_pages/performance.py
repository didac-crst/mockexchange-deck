"""performance.py

Streamlit page that displays the **performance** of MockExchange.

Key features
------------
* Pulls the most‑recent *N* trades from the REST back‑end (`get_trades_overview`).
* Lets the user interactively **filter** by trade *status*, *side*, *type* and *asset*.
* Persists those filters across automatic page refreshes – unless the
  user explicitly unfreezes them.
* Shows a colour‑coded dataframe where **freshly updated** rows are
  highlighted and slowly fade out (visual degradations).
* Optionally displays an "advanced" equity breakdown in the sidebar.

The code is intentionally verbose on comments to serve as a living
reference for new contributors.
"""

import os
import time  # noqa: F401  # imported for completeness – not used directly yet
from pathlib import Path
from dotenv import load_dotenv

import pandas as pd
import plotly.express as px
import streamlit as st
import plotly.graph_objects as go
import altair as alt

from app.services.api import get_orders, get_trades_overview
from ._helpers import (
    _display_performance_details,
    advanced_filter_toggle,
)
from ._colors import _row_style

# -----------------------------------------------------------------------------
# Configuration & constants
# -----------------------------------------------------------------------------
# Load environment variables from the project root .env so this file
# can be executed standalone (e.g. `streamlit run src/.../orders.py`).
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# How long a row stays "fresh" (seconds) → affects row colouring.
FRESH_WINDOW_S = int(os.getenv("FRESH_WINDOW_S", 300))  # default 5 min


# -----------------------------------------------------------------------------
# Main page renderer – Streamlit entry‑point
# -----------------------------------------------------------------------------

def render() -> None:  # noqa: D401 – imperative mood is clearer here
    """Render the **Order Book** page.

    Workflow
    --------
    """

    # Basic Streamlit page config
    st.set_page_config(page_title="Performance")  # browser tab + sidebar label
    st.title("Performance")

    # ------------------------------------------------------------------
    # Keep track of the auto‑refresh ticker so we can detect new reruns
    # ------------------------------------------------------------------
    curr_tick = st.session_state.get("refresh", 0)
    last_tick = st.session_state.get("_last_refresh_tick", None)

    # ------------------------------------------------------------------
    # 2) Fetch raw data from the API and pre‑process
    # ------------------------------------------------------------------
    base = os.getenv("UI_URL", "http://localhost:8000")


    trades_summary, cash_asset = get_trades_overview()

    # ------------------------------------------------------------------
    # Sidebar – advanced equity breakdown & toggle
    # ------------------------------------------------------------------

    advanced_display = advanced_filter_toggle()

    _display_performance_details(trades_summary, cash_asset, advanced_display)

    c1, c2 = st.columns(2)
    # Graph
    net_invested  = 10_000.00
    pnl_gross     =  -5_274.20   # example
    pnl_net       =  -5_864.85
    market_value  = net_invested + pnl_net
    with c1:
        fig = go.Figure(go.Waterfall(
            orientation="v",
            measure = ["absolute","relative","relative","total"],
            x = ["Net Investment","Gross P&L","Fees","Market Value"],
            y = [net_invested, pnl_gross, pnl_net - pnl_gross, market_value],
            textposition="outside"
        ))
        st.plotly_chart(fig, use_container_width=True)
    # ------------------------------------------------------------------
    # pie_df = pd.DataFrame({
    #     "metric": ["Net P&L", "Fees"],
    #     "value": [pnl_net, pnl_gross - pnl_net]
    # })
    # with c2:
    #     fig = px.pie(pie_df, names="metric", values="value", hole=0.4)
    #     fig.update_layout(
    #         autosize=True,  # fill container width
    #         margin=dict(t=40, b=40, l=40, r=40),
    #     )
    #     st.plotly_chart(fig, use_container_width=True)


    # Inputs
    net_invested  = 10_000.00
    pnl_net       = -5464.85
    market_value  = net_invested + pnl_net  # = 4535.15

    # Step 1: Decompose
    unrealized_gain = market_value - net_invested  # -5464.85
    realized_pnl = pnl_net - unrealized_gain       # 0.0
    realized_returns = net_invested + realized_pnl # 10_000.00

    # Step 2: Multiples
    dpi = realized_returns / net_invested          # = 1.0 (no loss realized)
    rvpi = market_value / net_invested             # = 0.45
    tvpi = dpi + rvpi                              # = 1.45

    # Step 3: Visualize in bar

    df = pd.DataFrame({
        "Multiple": ["DPI (Realized)", "RVPI (Unrealized)", "TVPI (Total)"],
        "Value": [dpi, rvpi, tvpi],
        "Color": ["#1f77b4", "#ff7f0e", "#2ca02c"]
    })

    bar = alt.Chart(df).mark_bar().encode(
        x="Multiple:N",
        y=alt.Y("Value:Q", scale=alt.Scale(domain=[0, max(tvpi * 1.1, 1.5)])),
        color=alt.Color("Multiple:N", scale=alt.Scale(range=df["Color"].tolist())),
        tooltip=[alt.Tooltip("Value:Q", format=".2f")]
    ).properties(title="Fund Performance Multiples (DPI / RVPI / TVPI)")

    st.altair_chart(bar, use_container_width=True)


    value_multiple = market_value / net_invested

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=[value_multiple],
        y=["Market Value vs Invested"],
        orientation="h",
        text=[f"{value_multiple:.2f}×"],
        textposition="auto",
        marker_color="green" if value_multiple >= 1 else "red"
    ))

    fig.add_shape(
        type="line",
        x0=1, x1=1, y0=-0.5, y1=0.5,
        line=dict(color="black", dash="dash"),
        name="Break-even"
    )

    fig.update_layout(
        title="Portfolio Value Multiple (× Invested Capital)",
        xaxis=dict(range=[0, max(1.5, value_multiple + 0.5)], title="Multiple"),
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True)
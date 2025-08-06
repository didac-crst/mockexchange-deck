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

from app.services.api import get_trades_overview,  get_overview_capital
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
    summary_capital = get_overview_capital()

    # ------------------------------------------------------------------
    # Sidebar – advanced equity breakdown & toggle
    # ------------------------------------------------------------------

    advanced_display = advanced_filter_toggle()

    # --- capital -------------------------------------------------
    equity = summary_capital.get("equity", 0.0)
    paid_in_capital = summary_capital.get("deposits", 0.0)
    distributions = summary_capital.get("withdrawals", 0.0)
    net_investment = paid_in_capital - distributions  # net invested capital

    # --- core amounts --------------------------------------------------
    incomplete_data        = trades_summary["TOTAL"]["amount_value_incomplete"]
    total_buys             = trades_summary["BUY"]["notional"]
    total_sells            = trades_summary["SELL"]["notional"]
    capital_market_exposed = total_buys - total_sells
    liquid_assets         = equity - capital_market_exposed  # cash + liquid assets
    total_paid_fees        = trades_summary["TOTAL"]["fee"]

    buy_current_value      = trades_summary["BUY"]["amount_value"] # Current value of all buy trades - even if part of them have already been sold
    sell_current_value     = trades_summary["SELL"]["amount_value"] # Current value of all sell trades - somehow is the missing opportunity value
    assets_current_value   = buy_current_value - sell_current_value # still held

    # --- cash & P&L figures -------------------------------------------
    gross_earnings         = equity - net_investment  # before fees
    net_earnings           = gross_earnings - total_paid_fees  # after fees



    # --- multiples (gross) --------------------------------------------
    rvpi_gross = equity / paid_in_capital if paid_in_capital > 0 else None # RVPI = Residual Value to Paid-In
    dpi_gross  = distributions / paid_in_capital if paid_in_capital > 0 else None # DPI = Distributions to Paid-In
    tvpi_gross = dpi_gross + rvpi_gross if None not in (dpi_gross, rvpi_gross) else None # TVPI = Total Value to Paid-In

    _display_performance_details(summary_capital, trades_summary, cash_asset, advanced_display)

    _CHART_BLUE = "#0f8ce5"  # blue
    _CHART_RED = "#f15151"  # red
    _CHART_GREEN = "#07bd10"  # green

    c1, c2 = st.columns(2)
    # Graph 1 --------------------------------------------------
    with c1:
        fig1 = go.Figure()

        gross_PL_color = _CHART_GREEN if gross_earnings >= 0 else _CHART_RED
        steps_fig1 = [
            # label              y-value                     measure      colour
            ("Paid-In-Capital",  paid_in_capital,            "absolute",  _CHART_BLUE),
            ("Gross P&L",        gross_earnings,             "relative",  gross_PL_color),
            ("Fees",            -total_paid_fees,            "relative",  _CHART_RED),
            ("Market Value",    -assets_current_value,       "relative",  _CHART_BLUE),
            ("Cash Assets",     -liquid_assets,              "relative",  _CHART_BLUE),
            ("Distributions",   -distributions,              "relative",  _CHART_BLUE),
        ]

        cum_base = 0
        for label, y_val, meas, colour in steps_fig1:
            fig1.add_trace(
                go.Waterfall(
                    x=[label],
                    y=[y_val],
                    measure=[meas],
                    base=cum_base if meas != "absolute" else None,
                    increasing=dict(marker=dict(color=colour)),
                    decreasing=dict(marker=dict(color=colour)),
                    totals=dict(marker=dict(color=colour)),
                    showlegend=False
                )
            )
            # Update running base for the next bar (only if not 'total')
            if meas != "total":
                cum_base += y_val

        fig1.update_layout(showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)

    # Graph 2 --------------------------------------------------
    with c2:
        fig2 = go.Figure()
        color_dpi = _CHART_BLUE
        color_rvpi = _CHART_GREEN if (equity >= net_investment) else _CHART_RED
        color_tvpi = _CHART_GREEN if tvpi_gross >= 1 else _CHART_RED
        steps_fig2 = [
            # label                  y-value                     measure      colour
            ("DPI (Realized)",       dpi_gross,                 "absolute",  color_dpi),
            ("RVPI (Unrealized)",    rvpi_gross,                "relative",  color_rvpi),
            ("TVPI (Total)",         -tvpi_gross,                "relative",  color_tvpi),
        ]

        cum_base = 0
        for label, y_val, meas, colour in steps_fig2:
            fig2.add_trace(
                go.Waterfall(
                    x=[label],
                    y=[y_val],
                    measure=[meas],
                    base=cum_base if meas != "absolute" else None,
                    increasing=dict(marker=dict(color=colour)),
                    decreasing=dict(marker=dict(color=colour)),
                    totals=dict(marker=dict(color=colour)),
                    showlegend=False
                )
            )
            # Update running base for the next bar (only if not 'total')
            if meas != "total":
                cum_base += y_val

        fig2.update_layout(showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)


        # color_dpi = _CHART_BLUE
        # color_rvpi = _CHART_GREEN if (equity >= net_investment) else _CHART_RED
        # color_tvpi = _CHART_GREEN if tvpi_gross >= 1 else _CHART_RED
        # fig2 = go.Figure(
        #     go.Waterfall(
        #         orientation="v",
        #         measure=["absolute", "relative", "total"],
        #         x=["DPI (Realized)", "RVPI (Unrealized)", "TVPI (Total)"],
        #         y=[dpi_gross, rvpi_gross, tvpi_gross],
        #         textposition="outside",
        #         marker=dict(
        #             color=[
        #                 color_dpi, color_rvpi, color_tvpi
        #             ]
        #         ),
        #     )
        # )

        # fig2.update_layout(showlegend=False)
        # st.plotly_chart(fig2, use_container_width=True)

        # # Inputs
        # net_invested  = 10_000.00
        # pnl_net       = -5464.85
        # market_value  = net_invested + pnl_net  # = 4535.15

        # # Step 1: Decompose
        # unrealized_gain = market_value - net_invested  # -5464.85
        # realized_pnl = pnl_net - unrealized_gain       # 0.0
        # realized_returns = net_invested + realized_pnl # 10_000.00

        # # Step 2: Multiples
        # dpi = realized_returns / net_invested          # = 1.0 (no loss realized)
        # rvpi = market_value / net_invested             # = 0.45
        # tvpi = dpi + rvpi                              # = 1.45

        # # Step 3: Visualize in bar

        # df = pd.DataFrame({
        #     "Multiple": ["DPI (Realized)", "RVPI (Unrealized)", "TVPI (Total)"],
        #     "Value": [dpi, rvpi, tvpi],
        #     "Color": ["#1f77b4", "#ff7f0e", "#2ca02c"]
        # })

        # bar = alt.Chart(df).mark_bar().encode(
        #     x="Multiple:N",
        #     y=alt.Y("Value:Q", scale=alt.Scale(domain=[0, max(tvpi * 1.1, 1.5)])),
        #     color=alt.Color("Multiple:N", scale=alt.Scale(range=df["Color"].tolist())),
        #     tooltip=[alt.Tooltip("Value:Q", format=".2f")]
        # ).properties(title="Fund Performance Multiples (DPI / RVPI / TVPI)")

        # st.altair_chart(bar, use_container_width=True)


    # value_multiple = market_value / net_invested

    # fig = go.Figure()

    # fig.add_trace(go.Bar(
    #     x=[value_multiple],
    #     y=["Market Value vs Invested"],
    #     orientation="h",
    #     text=[f"{value_multiple:.2f}×"],
    #     textposition="auto",
    #     marker_color="green" if value_multiple >= 1 else "red"
    # ))

    # fig.add_shape(
    #     type="line",
    #     x0=1, x1=1, y0=-0.5, y1=0.5,
    #     line=dict(color="black", dash="dash"),
    #     name="Break-even"
    # )

    # fig.update_layout(
    #     title="Portfolio Value Multiple (× Invested Capital)",
    #     xaxis=dict(range=[0, max(1.5, value_multiple + 0.5)], title="Multiple"),
    #     showlegend=False
    # )

    # st.plotly_chart(fig, use_container_width=True)
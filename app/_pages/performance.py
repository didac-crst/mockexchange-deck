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

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from app.services.api import get_orders, get_trades_overview
from ._helpers import (
    _human_ts,
    _add_details_column,
    _display_basic_trades_details,
    _display_advanced_trades_details,
    _format_significant_float,
    fmt_side_marker,
    TS_FMT,
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
    st.sidebar.header("Filters")
    advanced_display = st.sidebar.checkbox(
        "Display advanced details", value=False, key="advanced_display"
    )
    if advanced_display:
        st.sidebar.info(
            "Advanced details include metrics concerning total/buy/sell trades."
        )
        _display_basic_trades_details(trades_summary, cash_asset)
# _helpers.py

import pandas as pd
import streamlit as st


def _remove_small_zeros(num_str: str) -> str:
    """A number on a string, formatted to 6 decimal places.
    is parsed and the 0 on the right are removed until the units position.
    """
    try:
        # Parse the string as a float and format it
        return num_str.rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return num_str


def _add_history_column(
        df: pd.DataFrame,
        base_url: str,
        *,
        order_id_col: str = "id",
        new_col: str = "History",
        path_template: str = "/orders/{oid}/history",
    ) -> pd.DataFrame:
    """
    Return a copy of `df` with a new column `new_col` whose values are
    HTML links pointing at this order’s history.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame must contain a column `order_id_col`.
    base_url : str
        e.g. "http://localhost:8000"
    order_id_col : str
        Name of the column holding the Order ID strings.
    new_col : str
        Name for the new HTML-link column (default: "History").
    path_template : str
        A format string where "{oid}" is interpolated from the order ID.
    link_text : str
        The anchor text for the link (default: a small chain icon).

    Returns
    -------
    pd.DataFrame
        A fresh copy of `df` with `new_col` appended, containing raw
        `<a href=…>` strings.
    """
    df = df.copy()

    def make_url(oid: str) -> str:
        return base_url.rstrip("/") + path_template.format(oid=oid)

    df[new_col] = df[order_id_col].astype(str).map(make_url)
    return df
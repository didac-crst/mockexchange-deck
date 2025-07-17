"""Registry of Streamlit pages so main.py can route dynamically."""
from typing import Callable

from . import orders, portfolio

Page = Callable[[], None]

registry: dict[str, Page] = {
    "portfolio": portfolio.render,
    "orders": orders.render,
}

__all__ = ["registry"]
"""Registry of Streamlit pages so main.py can route dynamically."""
from typing import Callable

from . import dashboard, orders

Page = Callable[[], None]

registry: dict[str, Page] = {
    "Dashboard": dashboard.render,
    "Orders": orders.render,
}

__all__ = ["registry"]
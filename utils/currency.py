from __future__ import annotations

from flask import current_app


def format_money(amount, currency: str | None = None) -> str:
    """Format amount as PKR (Rs.) or USD ($) based on config or explicit currency."""
    try:
        val = float(amount)
    except (TypeError, ValueError):
        val = 0.0
    if currency is None and current_app:
        currency = str(current_app.config.get("CURRENCY", "PKR"))
    elif currency is None:
        currency = "PKR"
    code = currency.upper()
    if code == "USD":
        return f"${val:,.2f}"
    return f"Rs. {val:,.2f}"


def get_currency_code() -> str:
    if current_app:
        return str(current_app.config.get("CURRENCY", "PKR")).upper()
    return "PKR"

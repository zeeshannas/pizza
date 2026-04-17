from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from extensions import db
from models.order import Order
from models.order_item import OrderItem
from models.product import Product
from models.purchase import Purchase
from services.order_service import estimated_cogs_for_order_items


def _day_range(d: date) -> tuple[datetime, datetime]:
    start = datetime(d.year, d.month, d.day)
    end = start + timedelta(days=1)
    return start, end


def _month_range(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


def sales_summary(start: datetime, end: datetime) -> dict[str, Any]:
    q = select(func.coalesce(func.sum(Order.total), 0)).where(
        Order.created_at >= start,
        Order.created_at < end,
        Order.status != "cancelled",
    )
    revenue = float(db.session.execute(q).scalar() or 0)

    purchase_q = select(func.coalesce(func.sum(Purchase.cost), 0)).where(
        Purchase.created_at >= start,
        Purchase.created_at < end,
    )
    purchase_spend = float(db.session.execute(purchase_q).scalar() or 0)

    order_ids = (
        db.session.execute(
            select(Order.id).where(
                Order.created_at >= start,
                Order.created_at < end,
                Order.status != "cancelled",
            )
        )
        .scalars()
        .all()
    )
    total_cogs = 0.0
    for oid in order_ids:
        total_cogs += estimated_cogs_for_order_items(oid)

    profit = round(revenue - total_cogs, 2)

    return {
        "revenue": round(revenue, 2),
        "purchase_spend": round(purchase_spend, 2),
        "estimated_cogs": round(total_cogs, 2),
        "gross_profit": profit,
        "order_count": len(order_ids),
    }


def top_products(start: datetime, end: datetime, limit: int = 5) -> list[dict[str, Any]]:
    q = (
        select(
            Product.name,
            Product.size,
            func.sum(OrderItem.quantity).label("units"),
            func.sum(OrderItem.line_total).label("sales"),
        )
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(Order.created_at >= start, Order.created_at < end)
        .where(Order.status != "cancelled")
        .group_by(Product.id, Product.name, Product.size)
        .order_by(func.sum(OrderItem.line_total).desc())
        .limit(limit)
    )
    rows = db.session.execute(q).all()
    return [
        {
            "label": f"{r.name} ({r.size})",
            "units": int(r.units or 0),
            "sales": float(r.sales or 0),
        }
        for r in rows
    ]


def daily_report(day: date | None = None) -> dict[str, Any]:
    d = day or date.today()
    start, end = _day_range(d)
    base = sales_summary(start, end)
    base["label"] = d.isoformat()
    base["top_products"] = top_products(start, end)
    return base


def monthly_report(year: int | None = None, month: int | None = None) -> dict[str, Any]:
    today = date.today()
    y = year or today.year
    m = month or today.month
    start, end = _month_range(y, m)
    base = sales_summary(start, end)
    base["label"] = f"{y}-{m:02d}"
    base["top_products"] = top_products(start, end)
    return base


def revenue_last_n_days(n: int = 7) -> list[dict[str, Any]]:
    """Daily revenue for the last n calendar days (oldest first). Missing days are zero."""
    end = date.today()
    start = end - timedelta(days=n - 1)
    start_dt = datetime(start.year, start.month, start.day)
    end_dt = datetime(end.year, end.month, end.day) + timedelta(days=1)

    q = (
        select(
            func.date(Order.created_at).label("day"),
            func.coalesce(func.sum(Order.total), 0).label("revenue"),
        )
        .where(
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
            Order.status != "cancelled",
        )
        .group_by(func.date(Order.created_at))
    )
    raw: dict[str, float] = {}
    for row in db.session.execute(q).all():
        day_key = row.day
        if hasattr(day_key, "isoformat"):
            key = day_key.isoformat()
        else:
            key = str(day_key)
        raw[key] = float(row.revenue or 0)

    out: list[dict[str, Any]] = []
    d = start
    while d <= end:
        key = d.isoformat()
        rev = round(raw.get(key, 0.0), 2)
        out.append(
            {
                "date": d,
                "weekday": d.strftime("%a"),
                "revenue": rev,
            }
        )
        d += timedelta(days=1)
    return out

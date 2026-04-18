"""Cash position: sales (money in) vs inventory purchases (money out)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from extensions import db
from models.order import Order
from models.purchase import Purchase


def _order_paid_filters():
    return (Order.status != "cancelled", Order.payment_status == "paid")


def cash_flow_summary(start: datetime, end: datetime) -> dict[str, Any]:
    inflow = float(
        db.session.scalar(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.created_at >= start,
                Order.created_at < end,
                *_order_paid_filters(),
            )
        )
        or 0
    )
    outflow = float(
        db.session.scalar(
            select(func.coalesce(func.sum(Purchase.cost), 0)).where(
                Purchase.created_at >= start,
                Purchase.created_at < end,
            )
        )
        or 0
    )

    by_sale_method = (
        db.session.execute(
            select(Order.payment_method, func.coalesce(func.sum(Order.total), 0))
            .where(
                Order.created_at >= start,
                Order.created_at < end,
                *_order_paid_filters(),
            )
            .group_by(Order.payment_method)
            .order_by(Order.payment_method)
        )
        .all()
    )

    by_purchase_pay = (
        db.session.execute(
            select(Purchase.payment_method, func.coalesce(func.sum(Purchase.cost), 0))
            .where(
                Purchase.created_at >= start,
                Purchase.created_at < end,
            )
            .group_by(Purchase.payment_method)
            .order_by(Purchase.payment_method)
        )
        .all()
    )

    order_count = int(
        db.session.scalar(
            select(func.count(Order.id)).where(
                Order.created_at >= start,
                Order.created_at < end,
                *_order_paid_filters(),
            )
        )
        or 0
    )

    purchase_count = int(
        db.session.scalar(
            select(func.count(Purchase.id)).where(
                Purchase.created_at >= start,
                Purchase.created_at < end,
            )
        )
        or 0
    )

    return {
        "money_in": round(inflow, 2),
        "money_out": round(outflow, 2),
        "net_cash": round(inflow - outflow, 2),
        "order_count": order_count,
        "purchase_count": purchase_count,
        "sales_by_payment_method": [
            {"method": row[0] or "—", "total": float(row[1] or 0)} for row in by_sale_method
        ],
        "purchases_by_payment_method": [
            {"method": row[0] or "—", "total": float(row[1] or 0)} for row in by_purchase_pay
        ],
    }


def recent_paid_orders(start: datetime, end: datetime, limit: int = 40) -> list:
    return (
        db.session.execute(
            select(Order)
            .where(
                Order.created_at >= start,
                Order.created_at < end,
                *_order_paid_filters(),
            )
            .options(joinedload(Order.customer))
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        .unique()
        .scalars()
        .all()
    )


def recent_purchases(start: datetime, end: datetime, limit: int = 40) -> list:
    return (
        db.session.execute(
            select(Purchase)
            .where(
                Purchase.created_at >= start,
                Purchase.created_at < end,
            )
            .options(joinedload(Purchase.ingredient))
            .order_by(Purchase.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

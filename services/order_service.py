from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from extensions import db
from models.customer import Customer
from models.ingredient import Ingredient
from models.order import Order
from models.order_item import OrderItem
from models.product import Product
from models.product_ingredient import ProductIngredient


def _aggregate_quantities(items: list[dict[str, Any]]) -> dict[int, int]:
    out: dict[int, int] = defaultdict(int)
    for row in items:
        pid = int(row["product_id"])
        out[pid] += int(row["quantity"])
    return dict(out)


def validate_stock_for_order(items: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """items: [{product_id, quantity}, ...]"""
    agg = _aggregate_quantities(items)
    for product_id, qty in agg.items():
        product = db.session.get(Product, product_id)
        if not product or not product.is_active:
            return False, f"Product #{product_id} is not available."
        links = (
            db.session.execute(
                select(ProductIngredient).where(ProductIngredient.product_id == product_id)
            )
            .scalars()
            .all()
        )
        for link in links:
            ing = db.session.get(Ingredient, link.ingredient_id)
            if not ing:
                return False, "Ingredient configuration error."
            need = link.quantity_required * qty
            if ing.stock_qty < need:
                return False, f"Not enough {ing.name} in stock (need {need:.2f}, have {ing.stock_qty:.2f})."
    return True, None


def place_order(customer_id: int, items: list[dict[str, Any]], status: str = "completed") -> Order:
    """
    items: [{product_id, quantity}, ...]
    Raises ValueError on validation failure.
    """
    if not items:
        raise ValueError("Cart is empty.")

    customer = db.session.get(Customer, customer_id)
    if not customer:
        raise ValueError("Customer not found.")

    ok, msg = validate_stock_for_order(items)
    if not ok:
        raise ValueError(msg or "Stock validation failed.")

    total = 0.0
    priced_lines: list[dict[str, Any]] = []
    for row in items:
        pid = int(row["product_id"])
        q = int(row["quantity"])
        product = db.session.get(Product, pid)
        if not product:
            raise ValueError("Invalid product.")
        line_total = product.price * q
        total += line_total
        priced_lines.append(
            {
                "product_id": pid,
                "quantity": q,
                "price": product.price,
                "line_total": line_total,
            }
        )

    try:
        order = Order(customer_id=customer_id, total=round(total, 2), status=status)
        db.session.add(order)
        db.session.flush()

        for pl in priced_lines:
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=pl["product_id"],
                    quantity=pl["quantity"],
                    price=pl["price"],
                    line_total=pl["line_total"],
                )
            )

        agg = _aggregate_quantities(items)
        for product_id, qty in agg.items():
            links = (
                db.session.execute(
                    select(ProductIngredient).where(ProductIngredient.product_id == product_id)
                )
                .scalars()
                .all()
            )
            for link in links:
                ing = db.session.get(Ingredient, link.ingredient_id)
                need = link.quantity_required * qty
                ing.stock_qty = round(ing.stock_qty - need, 4)

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return (
        db.session.execute(
            select(Order).where(Order.id == order.id).options(joinedload(Order.items))
        )
        .unique()
        .scalar_one()
    )


def estimated_cogs_for_order_items(order_id: int) -> float:
    """Approximate COGS using current ingredient unit_cost."""
    order = db.session.get(Order, order_id)
    if not order:
        return 0.0
    cogs = 0.0
    for oi in order.items:
        links = (
            db.session.execute(
                select(ProductIngredient).where(ProductIngredient.product_id == oi.product_id)
            )
            .scalars()
            .all()
        )
        for link in links:
            ing = db.session.get(Ingredient, link.ingredient_id)
            if not ing:
                continue
            units = link.quantity_required * oi.quantity
            cogs += units * (ing.unit_cost or 0)
    return round(cogs, 2)

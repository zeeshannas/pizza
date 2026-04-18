from __future__ import annotations

from extensions import db
from models.ingredient import Ingredient
from models.purchase import Purchase


def record_purchase(
    ingredient_id: int,
    qty: float,
    total_cost: float,
    supplier_name: str | None = None,
    payment_method: str = "cash",
    payment_reference: str | None = None,
) -> Purchase:
    if qty <= 0:
        raise ValueError("Quantity must be positive.")
    if total_cost < 0:
        raise ValueError("Cost cannot be negative.")

    ing = db.session.get(Ingredient, ingredient_id)
    if not ing:
        raise ValueError("Ingredient not found.")

    unit_purchase_price = total_cost / qty
    old_qty = ing.stock_qty or 0.0
    old_cost = ing.unit_cost or 0.0
    new_qty = old_qty + qty

    if new_qty > 0:
        ing.unit_cost = round(
            (old_qty * old_cost + total_cost) / new_qty,
            4,
        )
    ing.stock_qty = round(new_qty, 4)

    pm = (payment_method or "cash").lower().strip()
    if pm not in ("cash", "bank", "card", "other"):
        raise ValueError("Invalid purchase payment method.")
    ref = (payment_reference or "").strip() or None

    p = Purchase(
        ingredient_id=ingredient_id,
        qty=qty,
        cost=round(total_cost, 2),
        supplier_name=supplier_name,
        payment_method=pm,
        payment_reference=ref,
    )
    db.session.add(p)
    db.session.commit()
    return p

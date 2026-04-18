from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import joinedload

from extensions import db
from models.customer import Customer
from models.ingredient import Ingredient
from models.order import Order
from models.order_item import OrderItem
from models.product import Product
from models.product_ingredient import ProductIngredient

WALLET_METHODS = frozenset({"jazzcash", "easypaisa", "meezan"})
FULFILLMENT_TYPES = frozenset({"dining", "takeaway", "delivery"})


def _normalize_fulfillment(fulfillment_type: str) -> str:
    ft = (fulfillment_type or "takeaway").lower().strip()
    if ft not in FULFILLMENT_TYPES:
        raise ValueError("Service type must be dining, takeaway, or delivery.")
    return ft


def _resolve_delivery_address(
    fulfillment_type: str, customer: Customer, delivery_address: str | None
) -> str | None:
    if fulfillment_type != "delivery":
        return None
    addr = (delivery_address or "").strip() or None
    if not addr and getattr(customer, "address", None):
        addr = (customer.address or "").strip() or None
    return addr


def _aggregate_quantities(items: list[dict[str, Any]]) -> dict[int, int]:
    out: dict[int, int] = defaultdict(int)
    for row in items:
        pid = int(row["product_id"])
        out[pid] += int(row["quantity"])
    return dict(out)


def _aggregate_from_order_items(order: Order) -> dict[int, int]:
    out: dict[int, int] = defaultdict(int)
    for oi in order.items:
        out[oi.product_id] += int(oi.quantity)
    return dict(out)


def _apply_inventory_for_aggregate(agg: dict[int, int], sign: int) -> None:
    """sign=+1 consume stock, sign=-1 return stock to inventory."""
    for product_id, qty in agg.items():
        if qty <= 0:
            continue
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
                continue
            need = link.quantity_required * qty
            delta = sign * need
            ing.stock_qty = round(ing.stock_qty - delta, 4)


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


def _validate_stock_delta(
    old_agg: dict[int, int], new_agg: dict[int, int]
) -> tuple[bool, str | None]:
    """Validate only the extra quantity needed vs old order."""
    all_ids = set(old_agg) | set(new_agg)
    delta_items: list[dict[str, Any]] = []
    for pid in all_ids:
        d = int(new_agg.get(pid, 0)) - int(old_agg.get(pid, 0))
        if d > 0:
            delta_items.append({"product_id": pid, "quantity": d})
    return validate_stock_for_order(delta_items)


def _build_priced_lines(items: list[dict[str, Any]]) -> tuple[float, list[dict[str, Any]]]:
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
    return round(total, 2), priced_lines


def _persist_order_items(order_id: int, priced_lines: list[dict[str, Any]]) -> None:
    db.session.execute(delete(OrderItem).where(OrderItem.order_id == order_id))
    for pl in priced_lines:
        db.session.add(
            OrderItem(
                order_id=order_id,
                product_id=pl["product_id"],
                quantity=pl["quantity"],
                price=pl["price"],
                line_total=pl["line_total"],
            )
        )


def place_order(
    customer_id: int,
    items: list[dict[str, Any]],
    *,
    status: str | None = None,
    payment_method: str = "cash",
    notes: str | None = None,
    fulfillment_type: str = "takeaway",
    delivery_address: str | None = None,
) -> Order:
    """
    items: [{product_id, quantity}, ...]
    Wallet methods create a pending order without deducting inventory until payment confirms.
    """
    if not items:
        raise ValueError("Cart is empty.")

    customer = db.session.get(Customer, customer_id)
    if not customer:
        raise ValueError("Customer not found.")

    pm = (payment_method or "cash").lower().strip()
    if pm not in ("cash", "card", "jazzcash", "easypaisa", "meezan"):
        raise ValueError("Invalid payment method.")

    ok, msg = validate_stock_for_order(items)
    if not ok:
        raise ValueError(msg or "Stock validation failed.")

    ft = _normalize_fulfillment(fulfillment_type)
    daddr = _resolve_delivery_address(ft, customer, delivery_address)
    if ft == "delivery" and not daddr:
        raise ValueError(
            "Delivery address is required. Save it on the customer or enter it for this order."
        )

    total, priced_lines = _build_priced_lines(items)
    wallet = pm in WALLET_METHODS
    if status is None:
        order_status = "pending_payment" if wallet else "completed"
    else:
        order_status = status
    pay_status = "pending" if wallet else "paid"

    try:
        order = Order(
            customer_id=customer_id,
            total=total,
            status=order_status,
            notes=(notes or "").strip() or None,
            payment_method=pm,
            payment_status=pay_status,
            inventory_applied=False if wallet else True,
            fulfillment_type=ft,
            delivery_address=daddr,
        )
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

        if not wallet:
            agg = _aggregate_quantities(items)
            _apply_inventory_for_aggregate(agg, +1)

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


def commit_order_after_wallet_payment(
    order_id: int, payment_reference: str | None = None
) -> Order:
    """Call after gateway success: deduct inventory and mark paid."""
    order = db.session.get(Order, order_id)
    if not order:
        raise ValueError("Order not found.")
    if order.payment_method not in WALLET_METHODS:
        raise ValueError("Order is not a wallet payment.")
    if order.payment_status == "paid" and order.inventory_applied:
        return order
    if order.status == "cancelled":
        raise ValueError("Order is cancelled.")

    agg = _aggregate_from_order_items(order)
    try:
        _apply_inventory_for_aggregate(agg, +1)
        order.inventory_applied = True
        order.payment_status = "paid"
        order.status = "completed"
        if payment_reference:
            order.payment_reference = payment_reference[:128]
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return (
        db.session.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(joinedload(Order.items), joinedload(Order.customer))
        )
        .unique()
        .scalar_one()
    )


def fail_wallet_order(order_id: int, reason: str | None = None) -> None:
    order = db.session.get(Order, order_id)
    if not order:
        return
    if order.payment_method not in WALLET_METHODS:
        return
    if order.inventory_applied:
        return
    order.payment_status = "failed"
    order.status = "cancelled"
    order.notes = _append_note(order.notes, reason or "Payment failed")
    db.session.commit()


def _append_note(existing: str | None, extra: str) -> str:
    extra = extra.strip()
    if not extra:
        return existing or ""
    if existing:
        return f"{existing}\n{extra}"[:500]
    return extra[:500]


def delete_order(order_id: int) -> None:
    """Remove order; restore inventory if it was already applied."""
    order = (
        db.session.execute(
            select(Order).where(Order.id == order_id).options(joinedload(Order.items))
        )
        .unique()
        .scalar_one_or_none()
    )
    if not order:
        raise ValueError("Order not found.")

    try:
        if order.inventory_applied:
            agg = _aggregate_from_order_items(order)
            _apply_inventory_for_aggregate(agg, -1)
        db.session.delete(order)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def update_order_contents(
    order_id: int,
    items: list[dict[str, Any]],
    *,
    notes: str | None = None,
    fulfillment_type: str | None = None,
    delivery_address: str | None = None,
) -> Order:
    """
    Replace order line items. Adjusts inventory when the order already consumed stock
    (cash/card completed orders). Pending wallet orders have no inventory yet — only lines change.
    """
    if not items:
        raise ValueError("Order must have at least one line.")

    order = (
        db.session.execute(
            select(Order).where(Order.id == order_id).options(joinedload(Order.items))
        )
        .unique()
        .scalar_one_or_none()
    )
    if not order:
        raise ValueError("Order not found.")
    if order.status == "cancelled":
        raise ValueError("Cancelled orders cannot be edited.")

    old_agg = _aggregate_from_order_items(order)
    new_agg = _aggregate_quantities(items)

    if order.inventory_applied:
        ok, msg = _validate_stock_delta(old_agg, new_agg)
        if not ok:
            raise ValueError(msg or "Stock validation failed.")

    total, priced_lines = _build_priced_lines(items)

    try:
        if order.inventory_applied:
            _apply_inventory_for_aggregate(old_agg, -1)
            _apply_inventory_for_aggregate(new_agg, +1)

        order.total = total
        if notes is not None:
            order.notes = notes.strip() or None
        if fulfillment_type is not None:
            order.fulfillment_type = _normalize_fulfillment(fulfillment_type)
        if fulfillment_type is not None or delivery_address is not None:
            cust = db.session.get(Customer, order.customer_id)
            if cust is None:
                raise ValueError("Customer not found.")
            ft = order.fulfillment_type
            daddr = _resolve_delivery_address(ft, cust, delivery_address)
            if ft == "delivery" and not daddr:
                raise ValueError("Delivery address is required for delivery orders.")
            order.delivery_address = daddr
        _persist_order_items(order.id, priced_lines)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return (
        db.session.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(joinedload(Order.items), joinedload(Order.customer))
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

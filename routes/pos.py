from flask import Blueprint, jsonify, render_template, request, url_for

from flask_login import login_required

from extensions import db
from models.customer import Customer
from models.product import Product
from services.order_service import WALLET_METHODS, place_order
from services.pakistan_payments import credentials_ready

pos_bp = Blueprint("pos", __name__, url_prefix="/pos")


@pos_bp.route("/")
@login_required
def pos_home():
    customers = Customer.query.order_by(Customer.name).limit(500).all()
    products = (
        Product.query.filter_by(is_active=True).order_by(Product.name, Product.size).all()
    )
    return render_template("pos/index.html", customers=customers, products=products)


@pos_bp.route("/checkout", methods=["POST"])
@login_required
def checkout():
    data = request.get_json(silent=True) or {}
    try:
        customer_id = int(data.get("customer_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid customer."}), 400
    raw_items = data.get("items") or []
    items = []
    for row in raw_items:
        try:
            items.append(
                {
                    "product_id": int(row.get("product_id")),
                    "quantity": int(row.get("quantity")),
                }
            )
        except (TypeError, ValueError):
            continue
    payment_method = (data.get("payment_method") or "cash").strip().lower()
    raw_notes = data.get("notes")
    if isinstance(raw_notes, str):
        notes = raw_notes.strip()[:500] or None
    else:
        notes = None
    fulfillment_type = (data.get("fulfillment_type") or "takeaway").strip().lower()
    da_raw = data.get("delivery_address")
    if isinstance(da_raw, str):
        delivery_address = da_raw.strip() or None
    else:
        delivery_address = None
    try:
        order = place_order(
            customer_id,
            items,
            payment_method=payment_method,
            notes=notes,
            fulfillment_type=fulfillment_type,
            delivery_address=delivery_address,
        )
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    out: dict = {
        "ok": True,
        "order_id": order.id,
        "total": order.total,
        "status": order.status,
        "payment_status": order.payment_status,
        "payment_method": order.payment_method,
        "fulfillment_type": order.fulfillment_type,
    }
    if order.payment_method in WALLET_METHODS:
        out["requires_payment"] = True
        out["wallet_checkout_url"] = url_for(
            "payments.wallet_checkout",
            oid=order.id,
            method=order.payment_method,
            _external=False,
        )
        out["credentials_configured"] = credentials_ready(order.payment_method)
    return jsonify(out)


@pos_bp.route("/customers/quick", methods=["POST"])
@login_required
def quick_add_customer():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip() or None
    if not name or not phone:
        return jsonify({"ok": False, "error": "Name and phone are required."}), 400
    existing = Customer.query.filter_by(phone=phone).first()
    if existing:
        return jsonify(
            {
                "ok": True,
                "existing": True,
                "customer": {
                    "id": existing.id,
                    "name": existing.name,
                    "phone": existing.phone,
                    "address": existing.address or "",
                },
            }
        )
    c = Customer(name=name, phone=phone, address=address)
    db.session.add(c)
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "existing": False,
            "customer": {
                "id": c.id,
                "name": c.name,
                "phone": c.phone,
                "address": c.address or "",
            },
        }
    )

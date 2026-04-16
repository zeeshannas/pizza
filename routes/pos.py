from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from extensions import db
from models.customer import Customer
from models.product import Product
from services.order_service import place_order

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
    try:
        order = place_order(customer_id, items)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify(
        {
            "ok": True,
            "order_id": order.id,
            "total": order.total,
        }
    )

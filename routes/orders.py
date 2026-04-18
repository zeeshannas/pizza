from io import BytesIO

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import login_required
from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from extensions import db
from models.order import Order
from models.order_item import OrderItem
from models.product import Product
from services.order_service import delete_order, update_order_contents
from utils.currency import format_money, get_currency_code

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")


@orders_bp.route("/")
@login_required
def list_orders():
    rows = (
        Order.query.options(joinedload(Order.customer))
        .order_by(Order.created_at.desc())
        .limit(150)
        .all()
    )
    return render_template("orders/list.html", orders=rows)


@orders_bp.route("/<int:oid>")
@login_required
def order_detail(oid: int):
    order = _load_order(oid)
    if not order:
        abort(404)
    products = (
        Product.query.filter_by(is_active=True).order_by(Product.name, Product.size).all()
    )
    return render_template("orders/detail.html", order=order, products=products)


@orders_bp.route("/<int:oid>/delete", methods=["POST"])
@login_required
def order_delete(oid: int):
    try:
        delete_order(oid)
        flash("Order deleted. Inventory was restored when stock had already been deducted.", "success")
        return redirect(url_for("orders.list_orders"))
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("orders.order_detail", oid=oid))


@orders_bp.route("/<int:oid>/update", methods=["POST"])
@login_required
def order_update(oid: int):
    data = request.get_json(silent=True) or {}
    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return jsonify({"ok": False, "error": "Invalid items."}), 400
    items: list[dict] = []
    for row in raw_items:
        try:
            items.append(
                {
                    "product_id": int(row["product_id"]),
                    "quantity": int(row["quantity"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    if not items:
        return jsonify({"ok": False, "error": "No valid lines."}), 400
    notes = data.get("notes")
    if not isinstance(notes, str):
        notes = None
    fulfillment_type = (
        data["fulfillment_type"]
        if "fulfillment_type" in data and isinstance(data["fulfillment_type"], str)
        else None
    )
    delivery_address = (
        data["delivery_address"]
        if "delivery_address" in data and isinstance(data["delivery_address"], str)
        else None
    )
    try:
        order = update_order_contents(
            oid,
            items,
            notes=notes,
            fulfillment_type=fulfillment_type,
            delivery_address=delivery_address,
        )
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify(
        {
            "ok": True,
            "order_id": order.id,
            "total": order.total,
        }
    )


@orders_bp.route("/<int:oid>/pdf")
@login_required
def order_pdf(oid: int):
    order = _load_order(oid)
    if not order:
        abort(404)
    cur = get_currency_code()
    pdf_bytes = _build_order_pdf(order, cur)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"olive-pizza-order-{oid}.pdf",
    )


def _load_order(oid: int) -> Order | None:
    stmt = (
        select(Order)
        .where(Order.id == oid)
        .options(
            joinedload(Order.customer),
            joinedload(Order.items).joinedload(OrderItem.product),
        )
    )
    return db.session.scalar(stmt)


def _build_order_pdf(order: Order, currency: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Olive Pizza", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "Order receipt", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(40, 7, "Order #", ln=0)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, str(order.id), ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(40, 7, "Date", ln=0)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, order.created_at.strftime("%Y-%m-%d %H:%M"), ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(40, 7, "Status", ln=0)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, order.status or "", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(40, 7, "Payment", ln=0)
    pdf.set_font("Helvetica", "", 11)
    pm = getattr(order, "payment_method", None) or "—"
    ps = getattr(order, "payment_status", None) or "—"
    pdf.cell(0, 7, _ascii_safe(f"{pm} / {ps}"), ln=True)

    ft = getattr(order, "fulfillment_type", None) or "takeaway"
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(40, 7, "Service", ln=0)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, _ascii_safe(ft.upper()), ln=True)
    if ft == "delivery" and getattr(order, "delivery_address", None):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(40, 7, "Deliver to", ln=0)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, _ascii_safe(order.delivery_address))

    cust = order.customer
    if cust:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(40, 7, "Customer", ln=0)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, f"{cust.name} ({cust.phone})", ln=True)
        if getattr(cust, "address", None) and ft != "delivery":
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(40, 7, "Address", ln=0)
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, _ascii_safe(cust.address))

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(100, 8, "Item", border="B")
    pdf.cell(25, 8, "Qty", border="B", align="R")
    pdf.cell(30, 8, "Price", border="B", align="R")
    pdf.cell(35, 8, "Line", border="B", align="R", ln=True)

    pdf.set_font("Helvetica", "", 10)
    for line in sorted(order.items, key=lambda x: x.id):
        prod = line.product
        label = prod.display_label() if prod else f"Product #{line.product_id}"
        if len(label) > 48:
            label = label[:45] + "..."
        pdf.cell(100, 7, _ascii_safe(label), border="B")
        pdf.cell(25, 7, str(line.quantity), border="B", align="R")
        pdf.cell(30, 7, format_money(line.price, currency), border="B", align="R")
        pdf.cell(35, 7, format_money(line.line_total, currency), border="B", align="R", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(155, 9, "Total", ln=0, align="R")
    pdf.cell(35, 9, format_money(order.total, currency), ln=True, align="R")

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, _ascii_safe("Thank you for your order."))

    out = pdf.output()
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    return str(out).encode("latin-1", errors="replace")


def _ascii_safe(text: str) -> str:
    """FPDF core fonts: keep Latin-1 safe for reliability."""
    if not text:
        return ""
    return text.encode("latin-1", errors="replace").decode("latin-1")

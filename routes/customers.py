from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import select

from extensions import db
from models.customer import Customer
from models.order import Order

customers_bp = Blueprint("customers", __name__, url_prefix="/customers")


@customers_bp.route("/")
@login_required
def list_customers():
    rows = Customer.query.order_by(Customer.name).all()
    return render_template("customers/list.html", customers=rows)


@customers_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_customer():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        if not name or not phone:
            flash("Name and phone are required.", "danger")
        else:
            addr = (request.form.get("address") or "").strip() or None
            c = Customer(name=name, phone=phone, address=addr)
            db.session.add(c)
            db.session.commit()
            flash("Customer saved.", "success")
            return redirect(url_for("customers.list_customers"))
    return render_template("customers/form.html", customer=None)


@customers_bp.route("/<int:cid>/edit", methods=["GET", "POST"])
@login_required
def edit_customer(cid: int):
    c = db.session.get(Customer, cid)
    if not c:
        flash("Not found.", "danger")
        return redirect(url_for("customers.list_customers"))
    if request.method == "POST":
        c.name = (request.form.get("name") or "").strip() or c.name
        c.phone = (request.form.get("phone") or "").strip() or c.phone
        c.address = (request.form.get("address") or "").strip() or None
        db.session.commit()
        flash("Customer updated.", "success")
        return redirect(url_for("customers.list_customers"))
    return render_template("customers/form.html", customer=c)


@customers_bp.route("/<int:cid>")
@login_required
def customer_detail(cid: int):
    c = db.session.get(Customer, cid)
    if not c:
        flash("Not found.", "danger")
        return redirect(url_for("customers.list_customers"))
    orders = (
        db.session.execute(select(Order).where(Order.customer_id == cid).order_by(Order.created_at.desc()))
        .scalars()
        .all()
    )
    return render_template("customers/detail.html", customer=c, orders=orders)

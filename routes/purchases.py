from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import select

from extensions import db
from models.ingredient import Ingredient
from models.purchase import Purchase
from services.purchase_service import record_purchase

purchases_bp = Blueprint("purchases", __name__, url_prefix="/purchases")


@purchases_bp.route("/")
@login_required
def list_purchases():
    rows = (
        db.session.execute(
            select(Purchase).order_by(Purchase.created_at.desc()).limit(200)
        )
        .scalars()
        .all()
    )
    return render_template("purchases/list.html", purchases=rows)


@purchases_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_purchase():
    ingredients = Ingredient.query.order_by(Ingredient.name).all()
    if request.method == "POST":
        try:
            ing_id = int(request.form.get("ingredient_id"))
            qty = float(request.form.get("qty"))
            total_cost = float(request.form.get("total_cost"))
            supplier = (request.form.get("supplier_name") or "").strip() or None
            record_purchase(ing_id, qty, total_cost, supplier_name=supplier)
            flash("Purchase recorded and inventory updated.", "success")
            return redirect(url_for("purchases.list_purchases"))
        except ValueError as e:
            flash(str(e), "danger")
    return render_template("purchases/form.html", ingredients=ingredients)

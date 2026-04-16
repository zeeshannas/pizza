from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from extensions import db
from models.ingredient import Ingredient
from models.product_ingredient import ProductIngredient
from utils.decorators import admin_required

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@inventory_bp.route("/")
@login_required
def list_ingredients():
    rows = Ingredient.query.order_by(Ingredient.name).all()
    return render_template("inventory/list.html", ingredients=rows)


@inventory_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_ingredient():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        stock = float(request.form.get("stock_qty") or 0)
        threshold = float(request.form.get("low_stock_threshold") or 10)
        unit_cost = float(request.form.get("unit_cost") or 0)
        if not name:
            flash("Name is required.", "danger")
        else:
            ing = Ingredient(
                name=name,
                stock_qty=stock,
                low_stock_threshold=threshold,
                unit_cost=unit_cost,
            )
            db.session.add(ing)
            db.session.commit()
            flash("Ingredient added.", "success")
            return redirect(url_for("inventory.list_ingredients"))
    return render_template("inventory/form.html", ingredient=None)


@inventory_bp.route("/<int:ing_id>/edit", methods=["GET", "POST"])
@login_required
def edit_ingredient(ing_id: int):
    ing = db.session.get(Ingredient, ing_id)
    if not ing:
        flash("Not found.", "danger")
        return redirect(url_for("inventory.list_ingredients"))
    if request.method == "POST":
        ing.name = (request.form.get("name") or "").strip() or ing.name
        ing.stock_qty = float(request.form.get("stock_qty") or ing.stock_qty)
        ing.low_stock_threshold = float(request.form.get("low_stock_threshold") or ing.low_stock_threshold)
        ing.unit_cost = float(request.form.get("unit_cost") or ing.unit_cost)
        db.session.commit()
        flash("Ingredient updated.", "success")
        return redirect(url_for("inventory.list_ingredients"))
    return render_template("inventory/form.html", ingredient=ing)


@inventory_bp.route("/<int:ing_id>/delete", methods=["POST"])
@admin_required
def delete_ingredient(ing_id: int):
    ing = db.session.get(Ingredient, ing_id)
    if ing:
        if ProductIngredient.query.filter_by(ingredient_id=ing_id).first():
            flash("Cannot delete: ingredient is used in product recipes.", "danger")
            return redirect(url_for("inventory.list_ingredients"))
        db.session.delete(ing)
        db.session.commit()
        flash("Ingredient removed.", "info")
    return redirect(url_for("inventory.list_ingredients"))

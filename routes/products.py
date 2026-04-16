from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import delete

from extensions import db
from models.ingredient import Ingredient
from models.product import Product
from models.product_ingredient import ProductIngredient
from utils.decorators import admin_required

products_bp = Blueprint("products", __name__, url_prefix="/products")

SIZES = ["S", "M", "L"]


@products_bp.route("/")
@login_required
def list_products():
    rows = Product.query.order_by(Product.name, Product.size).all()
    return render_template("products/list.html", products=rows)


@products_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_product():
    ingredients = Ingredient.query.order_by(Ingredient.name).all()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        size = (request.form.get("size") or "M").upper()
        price = float(request.form.get("price") or 0)
        active = request.form.get("is_active") == "on"
        if size not in SIZES:
            size = "M"
        if not name or price <= 0:
            flash("Valid name and price are required.", "danger")
        elif Product.query.filter_by(name=name, size=size).first():
            flash("This product & size combination already exists.", "danger")
        else:
            p = Product(name=name, size=size, price=price, is_active=active)
            db.session.add(p)
            db.session.flush()
            _save_ingredient_map(p.id, request.form)
            db.session.commit()
            flash("Product created.", "success")
            return redirect(url_for("products.list_products"))
    return render_template(
        "products/form.html",
        product=None,
        sizes=SIZES,
        ingredients=ingredients,
        mappings=[],
    )


@products_bp.route("/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def edit_product(pid: int):
    p = db.session.get(Product, pid)
    if not p:
        flash("Product not found.", "danger")
        return redirect(url_for("products.list_products"))
    ingredients = Ingredient.query.order_by(Ingredient.name).all()
    if request.method == "POST":
        p.name = (request.form.get("name") or "").strip() or p.name
        size = (request.form.get("size") or p.size).upper()
        p.size = size if size in SIZES else p.size
        p.price = float(request.form.get("price") or p.price)
        p.is_active = request.form.get("is_active") == "on"
        db.session.execute(delete(ProductIngredient).where(ProductIngredient.product_id == p.id))
        _save_ingredient_map(p.id, request.form)
        db.session.commit()
        flash("Product updated.", "success")
        return redirect(url_for("products.list_products"))
    mappings = ProductIngredient.query.filter_by(product_id=p.id).all()
    return render_template(
        "products/form.html",
        product=p,
        sizes=SIZES,
        ingredients=ingredients,
        mappings=mappings,
    )


@products_bp.route("/<int:pid>/delete", methods=["POST"])
@admin_required
def delete_product(pid: int):
    p = db.session.get(Product, pid)
    if p:
        db.session.delete(p)
        db.session.commit()
        flash("Product deleted.", "info")
    return redirect(url_for("products.list_products"))


def _save_ingredient_map(product_id: int, form) -> None:
    ids = form.getlist("ingredient_id")
    qtys = form.getlist("quantity_required")
    for i, ing_id in enumerate(ids):
        if not ing_id:
            continue
        try:
            q = float(qtys[i]) if i < len(qtys) else 0
        except (TypeError, ValueError):
            q = 0
        if q <= 0:
            continue
        db.session.add(
            ProductIngredient(
                product_id=product_id,
                ingredient_id=int(ing_id),
                quantity_required=q,
            )
        )

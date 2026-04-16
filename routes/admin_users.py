from flask import Blueprint, flash, redirect, render_template, request, url_for

from extensions import db
from models.user import User
from utils.decorators import admin_required

admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/admin/users")


@admin_users_bp.route("/")
@admin_required
def list_users():
    rows = User.query.order_by(User.role.desc(), User.name).all()
    return render_template("admin/users.html", users=rows)


@admin_users_bp.route("/add", methods=["POST"])
@admin_required
def add_user():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "staff").lower()
    if role not in ("admin", "staff"):
        role = "staff"
    if not name or not email or len(password) < 6:
        flash("Name, email and password (min 6 chars) are required.", "danger")
        return redirect(url_for("admin_users.list_users"))
    if User.query.filter_by(email=email).first():
        flash("Email already registered.", "danger")
        return redirect(url_for("admin_users.list_users"))
    u = User(name=name, email=email, role=role)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    flash("User created.", "success")
    return redirect(url_for("admin_users.list_users"))

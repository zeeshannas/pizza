from datetime import date, datetime, timedelta

from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func, select

from extensions import db
from models.ingredient import Ingredient
from models.order import Order
from services.report_service import daily_report, monthly_report

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def dashboard():
    low = (
        db.session.execute(
            select(Ingredient).where(Ingredient.stock_qty <= Ingredient.low_stock_threshold)
        )
        .scalars()
        .all()
    )
    today_stats = daily_report(date.today())
    month_stats = monthly_report()

    d0 = date.today()
    start = datetime(d0.year, d0.month, d0.day)
    end = start + timedelta(days=1)
    orders_today = int(
        db.session.execute(
            select(func.count(Order.id)).where(
                Order.created_at >= start,
                Order.created_at < end,
            )
        ).scalar()
        or 0
    )

    return render_template(
        "dashboard.html",
        low_stock=low,
        today=today_stats,
        month=month_stats,
        orders_today=orders_today,
    )

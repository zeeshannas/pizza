from datetime import date, datetime, timedelta

from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from extensions import db
from models.ingredient import Ingredient
from models.order import Order
from services.report_service import daily_report, monthly_report, revenue_last_n_days

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

    yesterday_stats = daily_report(date.today() - timedelta(days=1))
    week_revenue = revenue_last_n_days(7)
    max_day_rev = max((d["revenue"] for d in week_revenue), default=0.0)

    recent_orders = (
        db.session.execute(
            select(Order)
            .options(joinedload(Order.customer))
            .order_by(Order.created_at.desc())
            .limit(6)
        )
        .scalars()
        .all()
    )

    tr = float(today_stats["revenue"])
    yr = float(yesterday_stats["revenue"])
    if yr > 0:
        revenue_vs_yesterday_pct = round((tr - yr) / yr * 100, 1)
    elif tr > 0:
        revenue_vs_yesterday_pct = None
    else:
        revenue_vs_yesterday_pct = 0.0

    ot = int(orders_today)
    oy = int(yesterday_stats["order_count"])
    if oy > 0:
        orders_vs_yesterday_pct = round((ot - oy) / oy * 100, 1)
    elif ot > 0:
        orders_vs_yesterday_pct = None
    else:
        orders_vs_yesterday_pct = 0.0

    _now = datetime.now()
    return render_template(
        "dashboard.html",
        low_stock=low,
        today=today_stats,
        yesterday=yesterday_stats,
        month=month_stats,
        orders_today=orders_today,
        revenue_vs_yesterday_pct=revenue_vs_yesterday_pct,
        orders_vs_yesterday_pct=orders_vs_yesterday_pct,
        week_revenue=week_revenue,
        week_revenue_max=max_day_rev,
        recent_orders=recent_orders,
        hour_now=_now.hour,
        now=_now,
    )

from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request
from flask_login import login_required

from services.finance_service import cash_flow_summary, recent_paid_orders, recent_purchases

finance_bp = Blueprint("finance", __name__, url_prefix="/finance")


def _parse_range():
    today = date.today()
    start_s = request.args.get("start")
    end_s = request.args.get("end")
    if start_s and end_s:
        try:
            d0 = date.fromisoformat(start_s)
            d1 = date.fromisoformat(end_s)
        except ValueError:
            d0 = today.replace(day=1)
            d1 = today
    else:
        preset = request.args.get("preset") or "month"
        if preset == "today":
            d0 = d1 = today
        elif preset == "week":
            d0 = today - timedelta(days=6)
            d1 = today
        else:
            d0 = today.replace(day=1)
            d1 = today
    start_dt = datetime(d0.year, d0.month, d0.day)
    end_dt = datetime(d1.year, d1.month, d1.day) + timedelta(days=1)
    return start_dt, end_dt, d0, d1


@finance_bp.route("/")
@login_required
def finance_home():
    start_dt, end_dt, d0, d1 = _parse_range()
    summary = cash_flow_summary(start_dt, end_dt)
    orders_rows = recent_paid_orders(start_dt, end_dt)
    purchase_rows = recent_purchases(start_dt, end_dt)
    return render_template(
        "finance/index.html",
        summary=summary,
        orders_rows=orders_rows,
        purchase_rows=purchase_rows,
        range_start=d0,
        range_end=d1,
        preset=request.args.get("preset") or "month",
    )

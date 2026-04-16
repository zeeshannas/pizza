from datetime import date, datetime

from flask import Blueprint, render_template, request
from flask_login import login_required

from services.report_service import daily_report, monthly_report

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/")
@login_required
def reports_home():
    d_raw = request.args.get("day")
    m_raw = request.args.get("month")
    y_raw = request.args.get("year")

    today = date.today()
    if d_raw:
        try:
            day = datetime.fromisoformat(d_raw).date()
        except ValueError:
            day = today
    else:
        day = today

    try:
        month = int(m_raw) if m_raw else today.month
        year = int(y_raw) if y_raw else today.year
    except ValueError:
        month, year = today.month, today.year

    daily = daily_report(day)
    monthly = monthly_report(year, month)
    return render_template(
        "reports/index.html",
        daily=daily,
        monthly=monthly,
        selected_day=day.isoformat(),
        selected_month=month,
        selected_year=year,
    )

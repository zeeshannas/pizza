from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required

from extensions import db
from models.order import Order
from services.order_service import WALLET_METHODS, commit_order_after_wallet_payment, fail_wallet_order
from services.pakistan_payments import (
    build_easypaisa_form,
    build_jazzcash_form,
    build_meezan_payload,
    credentials_ready,
    parse_order_id_from_callback,
    verify_jazzcash_callback,
)

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


def _callback_base() -> str:
    """Use PUBLIC_BASE_URL in production so gateways hit the right host."""
    from flask import current_app

    base = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if base:
        return base
    return request.url_root.rstrip("/")


@payments_bp.route("/wallet/<int:oid>/<method>", methods=["GET"])
@login_required
def wallet_checkout(oid: int, method: str):
    method = method.lower()
    if method not in WALLET_METHODS:
        abort(404)
    order = db.session.get(Order, oid)
    if not order:
        abort(404)
    if order.payment_method != method:
        flash("Payment method does not match this order.", "danger")
        return redirect(url_for("orders.order_detail", oid=oid))
    if order.payment_status == "paid":
        flash("This order is already paid.", "info")
        return redirect(url_for("orders.order_detail", oid=oid))

    cb = f"{_callback_base()}{url_for('payments.gateway_callback', method=method)}"
    demo = not credentials_ready(method)

    if method == "jazzcash":
        pack = build_jazzcash_form(order, cb)
    elif method == "easypaisa":
        pack = build_easypaisa_form(order, cb)
    else:
        pack = build_meezan_payload(order, cb)

    return render_template(
        "payments/wallet.html",
        order=order,
        method=method,
        action_url=pack["action_url"],
        fields=pack.get("fields") or {},
        txn_ref=pack.get("txn_ref"),
        demo=demo,
    )


@payments_bp.route("/callback/<method>", methods=["GET", "POST"])
def gateway_callback(method: str):
    method = method.lower()
    if method not in WALLET_METHODS:
        abort(404)

    data = request.form.to_dict() if request.method == "POST" else request.args.to_dict()
    oid = parse_order_id_from_callback(data, method)
    if not oid:
        for alt in ("orderId", "order_id", "pp_BillReference"):
            raw = data.get(alt)
            if raw and "order_" in str(raw):
                try:
                    oid = int(str(raw).split("order_")[-1])
                except ValueError:
                    oid = None
            if oid:
                break

    if not oid:
        flash("Invalid payment callback.", "danger")
        return redirect(url_for("orders.list_orders"))

    order = db.session.get(Order, oid)
    if not order:
        abort(404)

    if method == "jazzcash" and credentials_ready("jazzcash"):
        ok_hash, err = verify_jazzcash_callback(data)
        if not ok_hash:
            fail_wallet_order(order.id, err or "Invalid JazzCash secure hash")
            flash("Payment verification failed.", "danger")
            return redirect(url_for("orders.order_detail", oid=oid))

    success = _response_successful(data, method)

    ref = (
        data.get("pp_TxnRefNo")
        or data.get("transactionId")
        or data.get("transaction_id")
        or data.get("reference")
        or data.get("orderId")
    )

    if success:
        try:
            commit_order_after_wallet_payment(order.id, str(ref) if ref else None)
            flash("Payment received. Order completed.", "success")
        except ValueError as e:
            flash(str(e), "danger")
    else:
        fail_wallet_order(order.id, "Gateway reported failure or hash check failed.")
        flash("Payment was not completed.", "warning")

    return redirect(url_for("orders.order_detail", oid=oid))


def _response_successful(data: dict, method: str) -> bool:
    """Best-effort status detection — align with your acquirer response fields."""
    if method == "jazzcash":
        code = str(data.get("pp_ResponseCode") or data.get("responseCode") or "").strip()
        if code in ("000", "0", "200"):
            return True
        msg = str(data.get("pp_ResponseMessage") or "").lower()
        return "success" in msg or "paid" in msg
    if method == "easypaisa":
        st = str(data.get("status") or data.get("responseCode") or "").lower()
        return st in ("000", "success", "paid", "completed")
    if method == "meezan":
        st = str(data.get("status") or data.get("resultCode") or "").lower()
        return st in ("0", "success", "ok", "approved", "completed")
    return False


@payments_bp.route("/demo/complete/<int:oid>", methods=["POST"])
@login_required
def demo_complete_payment(oid: int):
    """Sandbox: mark wallet order paid when live credentials are not configured."""
    order = db.session.get(Order, oid)
    if not order or order.payment_method not in WALLET_METHODS:
        abort(404)
    if credentials_ready(order.payment_method):
        flash("Demo completion is disabled while live credentials are set.", "warning")
        return redirect(url_for("orders.order_detail", oid=oid))
    try:
        commit_order_after_wallet_payment(oid, payment_reference="DEMO-LOCAL")
        flash("Demo payment applied. Inventory updated.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("orders.order_detail", oid=oid))

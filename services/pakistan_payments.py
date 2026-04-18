"""
Pakistani payment integrations (JazzCash, EasyPaisa, Meezan Bank).

These providers issue merchant credentials and documentation; this module implements
the usual request signing and callback verification patterns. Set credentials via
environment variables — without them, checkout falls back to a demo flow that
still exercises your app routes.

References: JazzCash / EasyPaisa merchant gateway docs (HMAC-SHA256, sorted fields).
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from models.order import Order


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _bool_env(name: str, default: bool = False) -> bool:
    v = _env(name).lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


@dataclass
class GatewayConfig:
    merchant_id: str
    password: str
    integrity_salt: str
    api_base: str
    sandbox: bool


def _jazz_config() -> GatewayConfig:
    return GatewayConfig(
        merchant_id=_env("JAZZCASH_MERCHANT_ID"),
        password=_env("JAZZCASH_PASSWORD"),
        integrity_salt=_env("JAZZCASH_INTEGRITY_SALT"),
        api_base=_env(
            "JAZZCASH_API_BASE",
            "https://sandbox.jazzcash.com.pk/CustomerPortal/merchantmanagement/MerchantSigned.aspx",
        ),
        sandbox=_bool_env("JAZZCASH_SANDBOX", True),
    )


def _ep_config() -> GatewayConfig:
    return GatewayConfig(
        merchant_id=_env("EASYPAISA_MERCHANT_ID"),
        password=_env("EASYPAISA_PASSWORD"),
        integrity_salt=_env("EASYPAISA_INTEGRITY_SALT", _env("EASYPAISA_STORE_ID")),
        api_base=_env(
            "EASYPAISA_API_BASE",
            "https://easypaystg.easypaisa.com.pk/easypay/Index.jsf",
        ),
        sandbox=_bool_env("EASYPAISA_SANDBOX", True),
    )


def _meezan_config() -> GatewayConfig:
    return GatewayConfig(
        merchant_id=_env("MEEZAN_MERCHANT_ID"),
        password=_env("MEEZAN_TERMINAL_KEY"),
        integrity_salt=_env("MEEZAN_INTEGRITY_SALT"),
        api_base=_env(
            "MEEZAN_API_BASE",
            "https://acquiring.meezanbank.com/payment/rest/register.do",
        ),
        sandbox=_bool_env("MEEZAN_SANDBOX", True),
    )


def jazzcash_secure_hash(fields: dict[str, Any], integrity_salt: str) -> str:
    """
    Typical JazzCash HMAC: sorted keys, exclude empty and pp_SecureHash,
    concatenate values with &, prefix salt, HMAC-SHA256 with salt as key.
    (Exact field order may follow your onboarding PDF — adjust if your bank differs.)
    """
    filtered: dict[str, str] = {}
    for k, v in fields.items():
        if k == "pp_SecureHash" or v is None or v == "":
            continue
        filtered[k] = str(v)
    parts = [integrity_salt]
    for key in sorted(filtered.keys()):
        parts.append(filtered[key])
    blob = "&".join(parts)
    return hmac.new(
        integrity_salt.encode("utf-8"),
        blob.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def easypaisa_hash(fields: dict[str, str], store_id: str) -> str:
    """EasyPaisa-style sorted concatenation + SHA256 (per merchant pack)."""
    filtered = {k: v for k, v in fields.items() if v not in (None, "") and k.lower() != "hash"}
    ordered = "&".join(f"{k}={filtered[k]}" for k in sorted(filtered.keys()))
    raw = f"{store_id}&{ordered}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_jazzcash_form(order: Order, return_url: str) -> dict[str, Any]:
    """
    Build fields for Merchant Hosted / signed checkout.
    Amount: many integrations use integer paisas (PKR * 100).
    """
    cfg = _jazz_config()
    txn_dt = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    txn_ref = f"OP{order.id}{txn_dt}"
    amount_minor = int(round(float(order.total) * 100))
    fields: dict[str, Any] = {
        "pp_Language": "EN",
        "pp_MerchantID": cfg.merchant_id,
        "pp_Password": cfg.password,
        "pp_TxnRefNo": txn_ref,
        "pp_Amount": str(amount_minor),
        "pp_TxnCurrency": "PKR",
        "pp_TxnDateTime": txn_dt,
        "pp_BillReference": f"order_{order.id}",
        "pp_Description": f"Olive Pizza Order #{order.id}",
        "pp_ReturnURL": return_url,
    }
    if cfg.merchant_id and cfg.integrity_salt:
        fields["pp_SecureHash"] = jazzcash_secure_hash(fields, cfg.integrity_salt)
    return {"action_url": cfg.api_base, "fields": fields, "txn_ref": txn_ref}


def build_easypaisa_form(order: Order, return_url: str) -> dict[str, Any]:
    cfg = _ep_config()
    oid = str(order.id)
    amt = f"{float(order.total):.2f}"
    fields = {
        "storeId": cfg.merchant_id,
        "amount": amt,
        "orderId": oid,
        "postBackURL": return_url,
        "merchantName": "Olive Pizza",
    }
    if cfg.merchant_id and cfg.integrity_salt:
        fields["hash"] = easypaisa_hash(fields, cfg.integrity_salt)
    return {"action_url": cfg.api_base, "fields": fields, "txn_ref": oid}


def build_meezan_payload(order: Order, return_url: str) -> dict[str, Any]:
    """
    Meezan Bank: replace api_base and field names with values from your merchant pack
    (hosted checkout vs REST). Values are stringified for HTML form POST.
    """
    cfg = _meezan_config()
    payload = {
        "userName": cfg.merchant_id,
        "password": cfg.password,
        "orderNumber": str(order.id),
        "amount": str(int(round(float(order.total) * 100))),
        "currency": "586",
        "returnUrl": return_url,
        "description": f"Order #{order.id}",
    }
    return {"action_url": cfg.api_base, "fields": payload, "txn_ref": str(order.id)}


def credentials_ready(method: str) -> bool:
    method = method.lower()
    if method == "jazzcash":
        c = _jazz_config()
        return bool(c.merchant_id and c.integrity_salt)
    if method == "easypaisa":
        c = _ep_config()
        return bool(c.merchant_id and c.integrity_salt)
    if method == "meezan":
        c = _meezan_config()
        return bool(c.merchant_id)
    return False


def verify_jazzcash_callback(post: dict[str, Any]) -> tuple[bool, str | None]:
    cfg = _jazz_config()
    if not cfg.integrity_salt:
        return False, "JazzCash not configured"
    received = post.get("pp_SecureHash") or post.get("secureHash")
    fields = {k: v for k, v in post.items() if k not in ("pp_SecureHash", "secureHash")}
    calc = jazzcash_secure_hash(fields, cfg.integrity_salt)
    if received and str(received).lower() == calc.lower():
        return True, None
    return False, "Hash mismatch"


def parse_order_id_from_callback(post: dict[str, Any], method: str) -> int | None:
    if method == "jazzcash":
        for key in ("pp_BillReference", "billreference"):
            raw = post.get(key) or post.get(key.upper())
            if raw and str(raw).startswith("order_"):
                try:
                    return int(str(raw).replace("order_", ""))
                except ValueError:
                    pass
        return None
    if method == "easypaisa":
        try:
            return int(post.get("orderId") or post.get("order_id") or 0)
        except (TypeError, ValueError):
            return None
    if method == "meezan":
        try:
            return int(post.get("orderNumber") or post.get("order_id") or 0)
        except (TypeError, ValueError):
            return None
    return None


def demo_mode_hint(method: str) -> dict[str, Any]:
    return {
        "demo": True,
        "message": (
            f"{method}: set merchant env vars (see config.py / pakistan_payments.py) "
            "to enable live redirects. You can still complete payment in demo mode."
        ),
    }

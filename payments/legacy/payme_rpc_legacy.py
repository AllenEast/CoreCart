# payments/api/payme_rpc.py
import base64
from decimal import Decimal
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError

from orders.models import Order
from payments.models import Payment
from payments.services.payment_service import PaymentService


def _unauthorized():
    return JsonResponse({"error": {"code": -32504, "message": "Unauthorized"}}, status=401)


def _jsonrpc_error(code: int, message: str, data=None, _id=None):
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    payload = {"error": err}
    if _id is not None:
        payload["id"] = _id
    return JsonResponse(payload, status=200)


def _jsonrpc_result(result, _id=None):
    payload = {"result": result}
    if _id is not None:
        payload["id"] = _id
    return JsonResponse(payload, status=200)


def _check_basic_auth(request) -> bool:
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Basic "):
        return False
    raw = auth.split(" ", 1)[1].strip()
    try:
        decoded = base64.b64decode(raw).decode("utf-8")
    except Exception:
        return False
    # Payme: login:password (merchant key)
    return decoded == settings.PAYME_BASIC_AUTH  # masalan: "Paycom:YOUR_KEY"


@csrf_exempt
@require_POST
def payme_rpc(request):
    if not _check_basic_auth(request):
        return _unauthorized()

    try:
        data = __import__("json").loads(request.body.decode("utf-8"))
    except Exception:
        return _jsonrpc_error(-32700, "Parse error")

    _id = data.get("id")
    method = data.get("method")
    params = data.get("params", {})

    # Senda account ichida order_id bo‘lsin deb kelishib olamiz:
    # masalan account: {"order_id": 123}
    account = params.get("account") or {}
    order_id = account.get("order_id")

    if method == "CheckPerformTransaction":
        # docs: allow true/false :contentReference[oaicite:3]{index=3}
        if not order_id:
            return _jsonrpc_error(-31050, "Invalid account", data="account.order_id", _id=_id)

        order = Order.objects.filter(pk=order_id).first()
        if not order:
            return _jsonrpc_error(-31050, "Order not found", data="account.order_id", _id=_id)

        # amount tiyinda keladi (Payme docs), bizda so‘m bo‘lsa conversion qiling
        amount_tiyin = params.get("amount")
        if amount_tiyin is None:
            return _jsonrpc_error(-31001, "Invalid amount", _id=_id)

        # Bu yerda o‘zing: order.total_price -> tiyinga mosligini tekshir
        return _jsonrpc_result({"allow": True}, _id=_id)

    if method == "CreateTransaction":
        if not order_id:
            return _jsonrpc_error(-31050, "Invalid account", data="account.order_id", _id=_id)

        order = Order.objects.filter(pk=order_id).first()
        if not order:
            return _jsonrpc_error(-31050, "Order not found", data="account.order_id", _id=_id)

        payment = PaymentService.create_payment(order=order, provider=Payment.PROVIDER_PAYME)
        payment.status = Payment.STATUS_PENDING
        payment.provider_payment_id = str(params.get("id"))  # Payme transaction id (params.id)
        payment.raw_request = data
        payment.save(update_fields=["status", "provider_payment_id", "raw_request", "updated_at"])

        # Payme response format: {result: {create_time, transaction, state}}
        # Bu yerini Payme docsga mos qilib to‘ldirasan (state mapping)
        return _jsonrpc_result(
            {"transaction": str(payment.id), "state": 1},
            _id=_id
        )

    if method == "PerformTransaction":
        # Payme transaction id: params.id
        provider_txn_id = str(params.get("id"))
        payment = Payment.objects.filter(provider=Payment.PROVIDER_PAYME, provider_payment_id=provider_txn_id).first()
        if not payment:
            return _jsonrpc_error(-31003, "Transaction not found", _id=_id)

        try:
            PaymentService.confirm_paid(payment=payment, provider_payment_id=provider_txn_id, raw_request=data)
        except ValidationError as e:
            return _jsonrpc_error(-32400, str(e), _id=_id)

        return _jsonrpc_result({"state": 2}, _id=_id)

    if method == "CancelTransaction":
        provider_txn_id = str(params.get("id"))
        payment = Payment.objects.filter(provider=Payment.PROVIDER_PAYME, provider_payment_id=provider_txn_id).first()
        if not payment:
            return _jsonrpc_error(-31003, "Transaction not found", _id=_id)

        try:
            PaymentService.cancel_payment(payment=payment, raw_request=data)
        except ValidationError as e:
            return _jsonrpc_error(-32400, str(e), _id=_id)

        return _jsonrpc_result({"state": -1}, _id=_id)

    return _jsonrpc_error(-32601, "Method not found", _id=_id)

# payments/api/click.py
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError

from orders.models import Order
from payments.models import Payment
from payments.services.payment_service import PaymentService


def _click_error(error: int, error_note: str):
    # Click response format docsga mos bo‘lsin
    return JsonResponse({"error": error, "error_note": error_note})


@csrf_exempt
@require_POST
@transaction.atomic
def click_pay(request):
    """
    Click server shu endpointga keladi:
    - action=0 (prepare)
    - action=1 (complete)
    """
    data = request.POST

    action = data.get("action")  # "0" or "1"
    order_id = data.get("merchant_trans_id")  # bizning order_id
    click_trans_id = data.get("click_trans_id")
    amount = data.get("amount")
    sign = data.get("sign_string")

    if not order_id or not click_trans_id:
        return _click_error(-1, "Invalid request")

    order = Order.objects.filter(pk=order_id).first()
    if not order:
        return _click_error(-5, "Order not found")

    # TODO: signature verify (Click docs bo‘yicha string yasab tekshirasan) :contentReference[oaicite:5]{index=5}
    # if not verify_click_signature(data, settings.CLICK_SECRET_KEY):
    #     return _click_error(-1, "SIGN CHECK FAILED")

    payment = PaymentService.create_payment(order=order, provider=Payment.PROVIDER_CLICK)
    payment.status = Payment.STATUS_PENDING
    payment.provider_payment_id = str(click_trans_id)
    payment.raw_request = dict(data)
    payment.save(update_fields=["status", "provider_payment_id", "raw_request", "updated_at"])

    if action == "0":
        # PREPARE: OK qaytarish
        return JsonResponse({"error": 0, "error_note": "Success", "merchant_prepare_id": payment.id})

    if action == "1":
        # COMPLETE: to‘lov muvaffaqiyatli bo‘lsa paid qilamiz
        try:
            PaymentService.confirm_paid(payment=payment, provider_payment_id=str(click_trans_id), raw_request=dict(data))
        except ValidationError as e:
            return _click_error(-9, str(e))

        return JsonResponse({"error": 0, "error_note": "Success", "merchant_confirm_id": payment.id})

    return _click_error(-3, "Unknown action")

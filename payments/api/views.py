# payments/api/views.py
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.conf import settings

from orders.models import Order
from payments.services.payment_service import PaymentService
from payments.api.serializers import PaymentSerializer
from payments.services.click_security import validate_signature


def _click_response(*, click_trans_id: str, merchant_trans_id: str, merchant_prepare_id: int | None, error: int, error_note: str):
    """Standard Click response payload (minimal)."""
    payload = {
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "error": int(error),
        "error_note": str(error_note),
    }
    if merchant_prepare_id is not None:
        payload["merchant_prepare_id"] = int(merchant_prepare_id)
    return payload


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def cod_create(request, order_id: int):
    order = get_object_or_404(Order, pk=order_id)

    if not request.user.is_staff and order.user_id != request.user.id:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    payment = PaymentService.get_or_create_cod_payment(order=order)
    return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])  # faqat admin/courier paid qiladi
def cod_mark_paid(request, order_id: int):
    order = get_object_or_404(Order, pk=order_id)
    payment = PaymentService.mark_cod_paid(order=order)
    return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def mock_pay(request, order_id: int):
    """DEV/TEST endpoint.

    Simulates a successful online payment (Click/Payme) without any external calls.
    Enabled ONLY when DEBUG=True.
    """

    if not settings.DEBUG:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    order = get_object_or_404(Order, pk=order_id)

    if not request.user.is_staff and order.user_id != request.user.id:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    payment = PaymentService.mark_mock_paid(order=order, raw_request={"by": str(request.user.id)})
    return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def mock_fail(request, order_id: int):
    """DEV/TEST endpoint.

    Simulates a failed payment.
    Enabled ONLY when DEBUG=True.
    """

    if not settings.DEBUG:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    order = get_object_or_404(Order, pk=order_id)

    if not request.user.is_staff and order.user_id != request.user.id:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    payment = PaymentService.mark_mock_failed(order=order, raw_request={"by": str(request.user.id)})
    return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


# ==============================
# CLICK (SHOP API) CALLBACKS
# ==============================


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def click_prepare(request):
    """Click 'Prepare' callback.

    Notes:
    - Click calls this endpoint without JWT.
    - In DEBUG mode, signature validation can be disabled.
    - In production (DEBUG=False), signature validation is required.

    Expected (common) fields in request.data:
      click_trans_id, service_id, merchant_trans_id, amount, action, sign_time, sign_string
    """

    data = dict(request.data)

    click_trans_id = str(data.get("click_trans_id", ""))
    merchant_trans_id = str(data.get("merchant_trans_id", ""))
    amount = str(data.get("amount", ""))

    # Basic required fields
    if not (click_trans_id and merchant_trans_id and amount):
        return Response(
            _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                merchant_prepare_id=None,
                error=-8,
                error_note="Missing required fields",
            ),
            status=status.HTTP_200_OK,
        )

    if not validate_signature(data, is_complete=False):
        return Response(
            _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                merchant_prepare_id=None,
                error=-1,
                error_note="SIGN CHECK FAILED",
            ),
            status=status.HTTP_200_OK,
        )

    # We map merchant_trans_id -> Order.id
    try:
        order_id = int(merchant_trans_id)
    except ValueError:
        return Response(
            _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                merchant_prepare_id=None,
                error=-5,
                error_note="Invalid merchant_trans_id",
            ),
            status=status.HTTP_200_OK,
        )

    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        return Response(
            _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                merchant_prepare_id=None,
                error=-5,
                error_note="Order not found",
            ),
            status=status.HTTP_200_OK,
        )

    # Optional: verify amount matches order.total_price
    try:
        req_amount = float(amount)
        ord_amount = float(order.total_price)
        if abs(req_amount - ord_amount) > 0.009:
            return Response(
                _click_response(
                    click_trans_id=click_trans_id,
                    merchant_trans_id=merchant_trans_id,
                    merchant_prepare_id=None,
                    error=-2,
                    error_note="Incorrect amount",
                ),
                status=status.HTTP_200_OK,
            )
    except Exception:
        # If amount parsing fails, we still proceed but record raw_request.
        pass

    payment = PaymentService.mark_click_prepared(
        order=order,
        click_trans_id=click_trans_id,
        amount=amount,
        raw_request={"provider": "click", "stage": "prepare", **data},
    )

    return Response(
        _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=payment.id,
            error=0,
            error_note="Success",
        ),
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def click_complete(request):
    """Click 'Complete' callback.

    Expected (common) fields:
      click_trans_id, service_id, merchant_trans_id, merchant_prepare_id, amount,
      action, sign_time, sign_string, error
    """

    data = dict(request.data)

    click_trans_id = str(data.get("click_trans_id", ""))
    merchant_trans_id = str(data.get("merchant_trans_id", ""))
    amount = str(data.get("amount", ""))
    merchant_prepare_id = str(data.get("merchant_prepare_id", ""))
    error = str(data.get("error", "0"))

    if not (click_trans_id and merchant_trans_id and amount and merchant_prepare_id):
        return Response(
            _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                merchant_prepare_id=None,
                error=-8,
                error_note="Missing required fields",
            ),
            status=status.HTTP_200_OK,
        )

    if not validate_signature(data, is_complete=True):
        return Response(
            _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                merchant_prepare_id=None,
                error=-1,
                error_note="SIGN CHECK FAILED",
            ),
            status=status.HTTP_200_OK,
        )

    try:
        order_id = int(merchant_trans_id)
    except ValueError:
        return Response(
            _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                merchant_prepare_id=None,
                error=-5,
                error_note="Invalid merchant_trans_id",
            ),
            status=status.HTTP_200_OK,
        )

    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        return Response(
            _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                merchant_prepare_id=None,
                error=-5,
                error_note="Order not found",
            ),
            status=status.HTTP_200_OK,
        )

    # Click sends error codes; 0 = success
    try:
        err_code = int(error)
    except ValueError:
        err_code = -8

    if err_code != 0:
        PaymentService.mark_click_failed(
            order=order,
            click_trans_id=click_trans_id,
            amount=amount,
            raw_request={"provider": "click", "stage": "complete", "error": err_code, **data},
        )
        return Response(
            _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                merchant_prepare_id=int(merchant_prepare_id) if merchant_prepare_id.isdigit() else None,
                error=err_code,
                error_note="Payment failed",
            ),
            status=status.HTTP_200_OK,
        )

    payment = PaymentService.mark_click_completed(
        order=order,
        click_trans_id=click_trans_id,
        merchant_prepare_id=merchant_prepare_id,
        amount=amount,
        raw_request={"provider": "click", "stage": "complete", **data},
    )

    return Response(
        _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=payment.id,
            error=0,
            error_note="Success",
        ),
        status=status.HTTP_200_OK,
    )

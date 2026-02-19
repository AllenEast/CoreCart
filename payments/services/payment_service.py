# payments/services/payment_service.py
import uuid

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from orders.models import Order
from orders.services.order_status_service import OrderStatusService
from payments.models import Payment


class PaymentService:
    @staticmethod
    @transaction.atomic
    def get_or_create_cod_payment(*, order: Order) -> Payment:
        order = Order.objects.select_for_update().get(pk=order.pk)

        payment, created = Payment.objects.get_or_create(
            order=order,
            defaults={
                "method": Payment.METHOD_COD,
                "amount": order.total_price,
                "status": Payment.STATUS_CREATED,
            },
        )

        if payment.method != Payment.METHOD_COD:
            raise ValidationError("This order already has a non-COD payment record.")

        if created or payment.amount != order.total_price:
            payment.amount = order.total_price
            payment.save(update_fields=["amount", "updated_at"])

        return payment

    # ✅ ALIAS: eski checkout_service chaqirsa ham 500 bo‘lmaydi
    @staticmethod
    def ensure_cod_payment(*, order: Order) -> Payment:
        return PaymentService.get_or_create_cod_payment(order=order)

    @staticmethod
    @transaction.atomic
    def mark_cod_paid(*, order: Order) -> Payment:
        order = Order.objects.select_for_update().get(pk=order.pk)

        payment = PaymentService.get_or_create_cod_payment(order=order)

        if payment.status == Payment.STATUS_PAID:
            return payment

        payment.status = Payment.STATUS_PAID
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "paid_at", "updated_at"])

        order.mark_paid()

        if order.status == Order.STATUS_PENDING:
            OrderStatusService.update_status(order_id=order.id, new_status=Order.STATUS_CONFIRMED)

        return payment

    @staticmethod
    @transaction.atomic
    def mark_mock_paid(*, order: Order, raw_request: dict | None = None) -> Payment:
        """DEV/TEST ONLY.

        Marks an order as paid without calling any external provider.
        Reuses the existing payment record (created during checkout) and switches
        its method to MOCK for clarity.
        """

        order = Order.objects.select_for_update().get(pk=order.pk)

        payment, _ = Payment.objects.get_or_create(
            order=order,
            defaults={
                "method": Payment.METHOD_MOCK,
                "amount": order.total_price,
                "status": Payment.STATUS_CREATED,
            },
        )

        # If checkout created COD payment, switch it to MOCK in dev/test.
        if payment.method != Payment.METHOD_MOCK:
            # allow switching only if not paid yet
            if payment.status == Payment.STATUS_PAID:
                return payment
            payment.method = Payment.METHOD_MOCK

        # Keep amount in sync
        if payment.amount != order.total_price:
            payment.amount = order.total_price

        if payment.status != Payment.STATUS_PAID:
            payment.status = Payment.STATUS_PAID
            payment.paid_at = timezone.now()
            payment.provider_ref = payment.provider_ref or f"MOCK-{uuid.uuid4()}"
            if raw_request is not None:
                payment.raw_request = raw_request
            payment.raw_response = {
                "ok": True,
                "provider": "mock",
                "provider_ref": payment.provider_ref,
                "paid_at": payment.paid_at.isoformat(),
            }
            payment.save(
                update_fields=[
                    "method",
                    "amount",
                    "status",
                    "paid_at",
                    "provider_ref",
                    "raw_request",
                    "raw_response",
                    "updated_at",
                ]
            )

        order.mark_paid()

        # Optional: auto-confirm when paid
        if order.status == Order.STATUS_PENDING:
            OrderStatusService.update_status(order_id=order.id, new_status=Order.STATUS_CONFIRMED)

        return payment

    @staticmethod
    @transaction.atomic
    def mark_mock_failed(*, order: Order, raw_request: dict | None = None) -> Payment:
        """DEV/TEST ONLY. Marks payment as failed."""

        order = Order.objects.select_for_update().get(pk=order.pk)

        payment, _ = Payment.objects.get_or_create(
            order=order,
            defaults={
                "method": Payment.METHOD_MOCK,
                "amount": order.total_price,
                "status": Payment.STATUS_CREATED,
            },
        )

        if payment.method != Payment.METHOD_MOCK and payment.status != Payment.STATUS_PAID:
            payment.method = Payment.METHOD_MOCK

        if payment.amount != order.total_price:
            payment.amount = order.total_price

        if payment.status != Payment.STATUS_PAID:
            payment.status = Payment.STATUS_FAILED
            payment.provider_ref = payment.provider_ref or f"MOCK-{uuid.uuid4()}"
            if raw_request is not None:
                payment.raw_request = raw_request
            payment.raw_response = {
                "ok": False,
                "provider": "mock",
                "provider_ref": payment.provider_ref,
            }
            payment.save(
                update_fields=[
                    "method",
                    "amount",
                    "status",
                    "provider_ref",
                    "raw_request",
                    "raw_response",
                    "updated_at",
                ]
            )

        return payment

    # ==============================
    # CLICK (SHOP API) - DEV/PROD
    # ==============================
    @staticmethod
    @transaction.atomic
    def mark_click_prepared(
        *,
        order: Order,
        click_trans_id: str,
        amount: str,
        raw_request: dict | None = None,
    ) -> Payment:
        """Create/update payment record for Click prepare step."""

        order = Order.objects.select_for_update().get(pk=order.pk)

        payment, _ = Payment.objects.get_or_create(
            order=order,
            defaults={
                "method": Payment.METHOD_CLICK,
                "amount": order.total_price,
                "status": Payment.STATUS_CREATED,
            },
        )

        # If order already paid, keep it paid.
        if payment.status == Payment.STATUS_PAID:
            return payment

        payment.method = Payment.METHOD_CLICK
        # keep amount in sync with order
        if payment.amount != order.total_price:
            payment.amount = order.total_price

        payment.status = Payment.STATUS_PENDING
        payment.provider_ref = click_trans_id or payment.provider_ref
        if raw_request is not None:
            payment.raw_request = raw_request
        payment.raw_response = {
            "ok": True,
            "provider": "click",
            "stage": "prepare",
            "click_trans_id": click_trans_id,
            "amount": amount,
        }
        payment.save(
            update_fields=[
                "method",
                "amount",
                "status",
                "provider_ref",
                "raw_request",
                "raw_response",
                "updated_at",
            ]
        )

        return payment

    @staticmethod
    @transaction.atomic
    def mark_click_completed(
        *,
        order: Order,
        click_trans_id: str,
        merchant_prepare_id: str,
        amount: str,
        raw_request: dict | None = None,
    ) -> Payment:
        """Marks Click payment as PAID and order as paid."""

        order = Order.objects.select_for_update().get(pk=order.pk)

        payment, _ = Payment.objects.get_or_create(
            order=order,
            defaults={
                "method": Payment.METHOD_CLICK,
                "amount": order.total_price,
                "status": Payment.STATUS_CREATED,
            },
        )

        # idempotent
        if payment.status != Payment.STATUS_PAID:
            payment.method = Payment.METHOD_CLICK
            if payment.amount != order.total_price:
                payment.amount = order.total_price
            payment.status = Payment.STATUS_PAID
            payment.paid_at = timezone.now()
            payment.provider_ref = click_trans_id or payment.provider_ref
            if raw_request is not None:
                payment.raw_request = raw_request
            payment.raw_response = {
                "ok": True,
                "provider": "click",
                "stage": "complete",
                "click_trans_id": click_trans_id,
                "merchant_prepare_id": merchant_prepare_id,
                "amount": amount,
                "paid_at": payment.paid_at.isoformat(),
            }
            payment.save(
                update_fields=[
                    "method",
                    "amount",
                    "status",
                    "paid_at",
                    "provider_ref",
                    "raw_request",
                    "raw_response",
                    "updated_at",
                ]
            )

        # Order paid + optional confirm
        order.mark_paid()
        if order.status == Order.STATUS_PENDING:
            OrderStatusService.update_status(order_id=order.id, new_status=Order.STATUS_CONFIRMED)

        return payment

    @staticmethod
    @transaction.atomic
    def mark_click_failed(
        *,
        order: Order,
        click_trans_id: str,
        amount: str,
        raw_request: dict | None = None,
    ) -> Payment:
        """Marks Click payment as FAILED."""

        order = Order.objects.select_for_update().get(pk=order.pk)

        payment, _ = Payment.objects.get_or_create(
            order=order,
            defaults={
                "method": Payment.METHOD_CLICK,
                "amount": order.total_price,
                "status": Payment.STATUS_CREATED,
            },
        )

        if payment.status != Payment.STATUS_PAID:
            payment.method = Payment.METHOD_CLICK
            if payment.amount != order.total_price:
                payment.amount = order.total_price
            payment.status = Payment.STATUS_FAILED
            payment.provider_ref = click_trans_id or payment.provider_ref
            if raw_request is not None:
                payment.raw_request = raw_request
            payment.raw_response = {
                "ok": False,
                "provider": "click",
                "stage": "fail",
                "click_trans_id": click_trans_id,
                "amount": amount,
            }
            payment.save(
                update_fields=[
                    "method",
                    "amount",
                    "status",
                    "provider_ref",
                    "raw_request",
                    "raw_response",
                    "updated_at",
                ]
            )

        return payment

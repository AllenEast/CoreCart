from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import ProductVariant
from orders.models import Order


class OrderStatusService:
    ALLOWED_TRANSITIONS = {
        Order.STATUS_PENDING: {Order.STATUS_CONFIRMED, Order.STATUS_CANCELLED},
        Order.STATUS_CONFIRMED: {Order.STATUS_SHIPPED, Order.STATUS_CANCELLED},
        Order.STATUS_SHIPPED: {Order.STATUS_DELIVERED},
        Order.STATUS_DELIVERED: set(),
        Order.STATUS_CANCELLED: set(),
    }

    @staticmethod
    @transaction.atomic
    def update_status(*, order_id: int, new_status: str) -> Order:
        order = (
            Order.objects
            .select_for_update()
            .prefetch_related("items")
            .get(pk=order_id)
        )

        # Valid status check
        if new_status not in dict(Order.STATUS_CHOICES):
            raise ValidationError("Invalid status")

        if new_status == order.status:
            return order  # idempotent

        # ✅ PAID bo‘lsa cancel yo‘q (refund yo‘q ekan)
        if new_status == Order.STATUS_CANCELLED and order.paid:
            raise ValidationError("Paid order cannot be cancelled (refund not implemented).")

        allowed = OrderStatusService.ALLOWED_TRANSITIONS.get(order.status, set())
        if new_status not in allowed:
            raise ValidationError(f"Cannot change status from {order.status} to {new_status}")

        # ✅ Cancel bo‘lsa stock qaytarish
        if new_status == Order.STATUS_CANCELLED:
            variant_ids = [i.variant_id for i in order.items.all()]
            variants = ProductVariant.objects.select_for_update().filter(id__in=variant_ids)
            vmap = {v.id: v for v in variants}

            for item in order.items.all():
                v = vmap.get(item.variant_id)
                if v:
                    v.stock_quantity += item.quantity

            ProductVariant.objects.bulk_update(variants, ["stock_quantity"])

        # IMPORTANT:
        # Order modeldagi set_status() barcha biznes qoidalarni (cancelled_at kabi)
        # bitta joyda saqlaydi. Service to'g'ridan-to'g'ri order.status ni qo'ymasligi kerak.
        order.set_status(new_status, save=True)
        return order

    @staticmethod
    @transaction.atomic
    def cancel_by_user(*, user, order_id: int) -> Order:
        """Cancel an order by its owner.

        Rules:
        - Only the order owner (or staff) can cancel.
        - Only PENDING and unpaid orders can be cancelled.
        - When cancelled, stock is returned.
        """

        order = (
            Order.objects
            .select_for_update()
            .prefetch_related("items")
            .get(pk=order_id)
        )

        if not (getattr(user, "is_staff", False) or order.user_id == user.id):
            raise ValidationError("You do not have permission to cancel this order.")

        if order.status == Order.STATUS_CANCELLED:
            return order  # idempotent

        if order.paid:
            raise ValidationError("Paid order cannot be cancelled (refund not implemented).")

        if order.status != Order.STATUS_PENDING:
            raise ValidationError("Only pending orders can be cancelled.")

        # Return stock
        variant_ids = [i.variant_id for i in order.items.all()]
        variants = ProductVariant.objects.select_for_update().filter(id__in=variant_ids)
        vmap = {v.id: v for v in variants}

        for item in order.items.all():
            v = vmap.get(item.variant_id)
            if v:
                v.stock_quantity += item.quantity

        ProductVariant.objects.bulk_update(variants, ["stock_quantity"])

        order.set_status(Order.STATUS_CANCELLED, save=True)
        return order

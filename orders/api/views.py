# orders/api/views.py
from django.core.exceptions import ValidationError
from drf_spectacular.utils import OpenApiResponse, extend_schema

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response

from orders.api.serializers import (
    CheckoutRequestSerializer,
    OrderSerializer,
    UpdateStatusRequestSerializer,
)
from orders.models import Order
from orders.services.checkout_service import CheckoutService
from orders.services.order_status_service import OrderStatusService


@extend_schema(
    tags=["Orders"],
    summary="Checkout: create order from current user's cart (COD)",
    request=CheckoutRequestSerializer,
    responses={
        200: OrderSerializer,
        400: OpenApiResponse(description="Bad request"),
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def checkout(request):
    ser = CheckoutRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    try:
        order = CheckoutService.checkout(
            user=request.user,
            phone=ser.validated_data["phone"],
            address=ser.validated_data["address"],
            comment=ser.validated_data.get("comment", ""),
        )
    except ValueError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    order = Order.objects.prefetch_related("items", "items__variant").get(pk=order.pk)
    return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none() if hasattr(self, 'queryset') and self.queryset is not None else Order.objects.none()
        qs = (
            Order.objects
            .prefetch_related("items", "items__variant")
            .order_by("-created_at")
        )
        if self.request.user.is_staff:
            return qs
        return qs.filter(user=self.request.user)

    @extend_schema(
        tags=["Orders"],
        summary="Admin: update order status (and return stock if cancelled)",
        request=UpdateStatusRequestSerializer,
        responses={
            200: OrderSerializer,
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    @action(
        detail=True,
        methods=["patch"],
        permission_classes=[permissions.IsAdminUser],
        url_path="update_status",
    )
    def update_status(self, request, pk=None):
        order = self.get_object()

        ser = UpdateStatusRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            order = OrderStatusService.update_status(
                order_id=order.id,
                new_status=ser.validated_data["status"],
            )
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.prefetch_related("items", "items__variant").get(pk=order.pk)
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Orders"],
        summary="User: cancel own order (only pending & unpaid; returns stock)",
        responses={
            200: OrderSerializer,
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="cancel",
    )
    def cancel(self, request, pk=None):
        order = self.get_object()

        try:
            order = OrderStatusService.cancel_by_user(user=request.user, order_id=order.id)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.prefetch_related("items", "items__variant").get(pk=order.pk)
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)

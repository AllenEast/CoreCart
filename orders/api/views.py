from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from orders.api.serializers import CheckoutRequestSerializer, OrderSerializer
from orders.services.checkout_service import CheckoutService
from orders.models import Order

from rest_framework import viewsets, permissions, decorators
from rest_framework.response import Response
from rest_framework import status

from orders.models import Order
from orders.api.serializers import OrderSerializer


@extend_schema(
    tags=["Orders"],
    summary="Checkout: create order from current user's cart",
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
    serializer = CheckoutRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        order = CheckoutService.checkout(
            user=request.user,
            phone=serializer.validated_data["phone"],
            address=serializer.validated_data["address"],
            comment=serializer.validated_data.get("comment", ""),
        )
    except ValueError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # items bilan qaytarish (bulk_create bo‘lgani uchun reload)
    order = (
        Order.objects
        .prefetch_related("items")
        .get(pk=order.pk)
    )

    return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    - GET /api/orders/        → user's orders
    - GET /api/orders/{id}/   → order detail
    """

    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Faqat o‘z orderlarini ko‘radi
        return (
            Order.objects
            .filter(user=self.request.user)
            .prefetch_related("items")
            .order_by("-created_at")
        )

    @decorators.action(
        detail=True,
        methods=["patch"],
        permission_classes=[permissions.IsAdminUser],
    )
    def update_status(self, request, pk=None):
        order = self.get_object()

        new_status = request.data.get("status")
        if not new_status:
            return Response(
                {"detail": "status is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_statuses = [choice[0] for choice in Order.STATUS_CHOICES]

        if new_status not in valid_statuses:
            return Response(
                {"detail": "Invalid status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = new_status
        order.save(update_fields=["status"])

        return Response(OrderSerializer(order).data)

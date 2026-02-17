from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from orders.api.serializers import CheckoutRequestSerializer, OrderSerializer
from orders.services.checkout_service import CheckoutService
from orders.models import Order


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

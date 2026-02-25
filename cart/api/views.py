from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from cart.api.serializers import (
    CartSerializer,
    AddToCartRequestSerializer,
    ChangeQuantityRequestSerializer,
    RemoveFromCartRequestSerializer,
)
from cart.services.cart_service import CartService
from cart.models import Cart


def _get_cart_response(user):
    cart = CartService.get_or_create_cart(user)
    cart = (
        Cart.objects
        .prefetch_related("items__variant__product", "items__variant__discount")
        .get(pk=cart.pk)
    )
    return Response(CartSerializer(cart).data)


@extend_schema(
    tags=["Cart"],
    summary="Get current user's cart",
    responses={200: CartSerializer},
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def cart_detail(request):
    return _get_cart_response(request.user)


@extend_schema(
    tags=["Cart"],
    summary="Add variant to cart",
    request=AddToCartRequestSerializer,
    responses={
        200: CartSerializer,
        400: OpenApiResponse(description="Bad request"),
    },
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])  # ✅ AllowAny emas
def cart_add(request):
    ser = AddToCartRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    try:
        CartService.add_to_cart(
            request.user,
            variant_id=ser.validated_data["variant_id"],
            quantity=ser.validated_data["quantity"],
        )
    except ValueError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return _get_cart_response(request.user)


@extend_schema(
    tags=["Cart"],
    summary="Change quantity of a variant in cart (0 => remove item)",
    request=ChangeQuantityRequestSerializer,
    responses={
        200: CartSerializer,
        400: OpenApiResponse(description="Bad request"),
    },
)
@api_view(["PATCH"])
@permission_classes([permissions.IsAuthenticated])
def cart_change_quantity(request):
    ser = ChangeQuantityRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    try:
        CartService.change_quantity(
            request.user,
            variant_id=ser.validated_data["variant_id"],
            quantity=ser.validated_data["quantity"],
        )
    except ValueError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return _get_cart_response(request.user)


@extend_schema(
    tags=["Cart"],
    summary="Remove variant from cart",
    request=RemoveFromCartRequestSerializer,
    responses={
        200: CartSerializer,
        400: OpenApiResponse(description="Bad request"),
    },
)
@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def cart_remove(request):
    ser = RemoveFromCartRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    CartService.remove_from_cart(
        request.user,
        variant_id=ser.validated_data["variant_id"],
    )
    return _get_cart_response(request.user)


@extend_schema(
    tags=["Cart"],
    summary="Clear cart",
    request=None,
    responses={200: CartSerializer},
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def cart_clear(request):
    CartService.clear_cart(request.user)
    return _get_cart_response(request.user)



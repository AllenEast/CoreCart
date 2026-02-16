from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from cart.api.serializers import CartSerializer
from cart.services.cart_service import CartService


@extend_schema(
    tags=["Cart"],
    summary="Get current user's cart",
    responses={200: CartSerializer},
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def cart_detail(request):
    cart = CartService.get_or_create_cart(request.user)
    # N+1 oldini olish (serializer o'zgarmaydi)
    cart = (
        cart.__class__.objects
        .prefetch_related("items__variant__product", "items__variant__discount")
        .get(pk=cart.pk)
    )
    return Response(CartSerializer(cart).data)


@extend_schema(
    tags=["Cart"],
    summary="Add variant to cart",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "variant_id": {"type": "integer"},
                "quantity": {"type": "integer", "default": 1},
            },
            "required": ["variant_id"],
        }
    },
    responses={
        200: CartSerializer,
        400: OpenApiResponse(description="Bad request"),
        404: OpenApiResponse(description="Variant not found"),
    },
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def cart_add(request):
    variant_id = request.data.get("variant_id")
    quantity = request.data.get("quantity", 1)

    if variant_id is None:
        return Response({"detail": "variant_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        variant_id = int(variant_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return Response({"detail": "variant_id and quantity must be integers"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        CartService.add_to_cart(request.user, variant_id=variant_id, quantity=quantity)
    except ValueError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    cart = CartService.get_or_create_cart(request.user)
    cart = (
        cart.__class__.objects
        .prefetch_related("items__variant__product", "items__variant__discount")
        .get(pk=cart.pk)
    )
    return Response(CartSerializer(cart).data)


@extend_schema(
    tags=["Cart"],
    summary="Change quantity of a variant in cart",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "variant_id": {"type": "integer"},
                "quantity": {"type": "integer"},
            },
            "required": ["variant_id", "quantity"],
        }
    },
    responses={200: CartSerializer, 400: OpenApiResponse(description="Bad request")},
)
@api_view(["PATCH"])
@permission_classes([permissions.IsAuthenticated])
def cart_change_quantity(request):
    variant_id = request.data.get("variant_id")
    quantity = request.data.get("quantity")

    if variant_id is None or quantity is None:
        return Response(
            {"detail": "variant_id and quantity are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        variant_id = int(variant_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return Response({"detail": "variant_id and quantity must be integers"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        CartService.change_quantity(request.user, variant_id=variant_id, quantity=quantity)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    cart = CartService.get_or_create_cart(request.user)
    cart = (
        cart.__class__.objects
        .prefetch_related("items__variant__product", "items__variant__discount")
        .get(pk=cart.pk)
    )
    return Response(CartSerializer(cart).data)


@extend_schema(
    tags=["Cart"],
    summary="Remove variant from cart",
    request={
        "application/json": {
            "type": "object",
            "properties": {"variant_id": {"type": "integer"}},
            "required": ["variant_id"],
        }
    },
    responses={200: CartSerializer, 400: OpenApiResponse(description="Bad request")},
)
@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def cart_remove(request):
    variant_id = request.data.get("variant_id")

    if variant_id is None:
        return Response({"detail": "variant_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        variant_id = int(variant_id)
    except (TypeError, ValueError):
        return Response({"detail": "variant_id must be integer"}, status=status.HTTP_400_BAD_REQUEST)

    CartService.remove_from_cart(request.user, variant_id=variant_id)

    cart = CartService.get_or_create_cart(request.user)
    cart = (
        cart.__class__.objects
        .prefetch_related("items__variant__product", "items__variant__discount")
        .get(pk=cart.pk)
    )
    return Response(CartSerializer(cart).data)


@extend_schema(
    tags=["Cart"],
    summary="Clear cart",
    responses={200: CartSerializer},
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def cart_clear(request):
    CartService.clear_cart(request.user)

    cart = CartService.get_or_create_cart(request.user)
    cart = (
        cart.__class__.objects
        .prefetch_related("items__variant__product", "items__variant__discount")
        .get(pk=cart.pk)
    )
    return Response(CartSerializer(cart).data)

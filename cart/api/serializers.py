from rest_framework import serializers
from cart.models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="variant.product.name",
        read_only=True
    )
    variant_id = serializers.IntegerField(source="variant.id", read_only=True)
    unit_price = serializers.DecimalField(
        source="get_unit_price",
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = CartItem
        fields = [
            "id",
            "variant_id",
            "product_name",
            "quantity",
            "unit_price",
            "total_price",
        ]

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total_price",
            "created_at",
            "updated_at",
        ]


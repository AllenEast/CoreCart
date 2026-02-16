from rest_framework import serializers
from cart.models import Cart, CartItem

from rest_framework import serializers
from catalog.models import ProductVariant



class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="variant.product.name",
        read_only=True
    )
    variant_id = serializers.IntegerField(source="variant.id", read_only=True)
    unit_price = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

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

    def get_unit_price(self, obj):
        return obj.get_unit_price()

    def get_total_price(self, obj):
        return obj.total_price


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total_price",
            "created_at",
            "updated_at",
        ]

    def get_total_price(self, obj):
        return obj.total_price



class AddToCartRequestSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate_variant_id(self, value: int):
        if not ProductVariant.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Variant not found or inactive.")
        return value


class ChangeQuantityRequestSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=0)  # 0 bo'lsa o'chiramiz

    def validate_variant_id(self, value: int):
        if not ProductVariant.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Variant not found or inactive.")
        return value


class RemoveFromCartRequestSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField()

    def validate_variant_id(self, value: int):
        if not ProductVariant.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Variant not found or inactive.")
        return value

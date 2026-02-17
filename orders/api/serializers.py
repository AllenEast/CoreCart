from rest_framework import serializers
from orders.models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "variant",        # id qaytadi
            "sku",
            "product_name",
            "variant_name",
            "unit_price",
            "quantity",
            "total_price",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "total_price",
            "phone",
            "address",
            "comment",
            "paid",
            "paid_at",
            "created_at",
            "updated_at",
            "items",
        ]


class CheckoutRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    address = serializers.CharField()
    comment = serializers.CharField(required=False, allow_blank=True, default="")

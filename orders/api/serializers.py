# orders/api/serializers.py
from rest_framework import serializers
from orders.models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    variant_id = serializers.IntegerField(source="variant.id", read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "variant_id",
            "sku",
            "product_name",
            "variant_name",
            "unit_price",
            "quantity",
            "total_price",
        ]

    def get_total_price(self, obj):
        return obj.total_price


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
            "cancelled_at",
            "created_at",
            "updated_at",
            "items",
        ]


class CheckoutRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    address = serializers.CharField()
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class UpdateStatusRequestSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)

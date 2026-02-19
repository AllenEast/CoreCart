from rest_framework import serializers
from payments.models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "method",
            "amount",
            "status",
            "paid_at",
            "provider_ref",
            "created_at",
            "updated_at",
        ]

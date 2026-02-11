import django_filters
from catalog.models import Product

class ProductFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name="subcategory__category__slug", lookup_expr="iexact")
    subcategory = django_filters.CharFilter(field_name="subcategory__slug", lookup_expr="iexact")
    brand = django_filters.CharFilter(field_name="brand__slug", lookup_expr="iexact")

    min_price = django_filters.NumberFilter(field_name="variants__price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="variants__price", lookup_expr="lte")

    class Meta:
        model = Product
        fields = ["category", "subcategory", "brand", "min_price", "max_price"]

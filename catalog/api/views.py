from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema, extend_schema_view
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from .filters import ProductFilter


from catalog.models import Category, SubCategory, Brand, Product, ProductVariant
from .serializers import (
    CategoryListSerializer,
    CategoryDetailSerializer,
    SubCategorySerializer,
    BrandSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductVariantSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=["Catalog"], summary="List active categories"),
    retrieve=extend_schema(tags=["Catalog"], summary="Get category by slug"),
)
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        return (
            Category.objects.filter(is_active=True)
            .prefetch_related("subcategories")
            .order_by("order", "name")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CategoryDetailSerializer
        return CategoryListSerializer


@extend_schema_view(
    list=extend_schema(tags=["Catalog"], summary="List active subcategories"),
    retrieve=extend_schema(tags=["Catalog"], summary="Get subcategory by slug"),
)
class SubCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        return (
            SubCategory.objects.filter(is_active=True)
            .select_related("category")
            .order_by("order", "name")
        )

    serializer_class = SubCategorySerializer


@extend_schema_view(
    list=extend_schema(tags=["Catalog"], summary="List brands"),
    retrieve=extend_schema(tags=["Catalog"], summary="Get brand by slug"),
)
class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.all().order_by("name")
    serializer_class = BrandSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"


@extend_schema_view(
    list=extend_schema(tags=["Catalog"], summary="List products"),
    retrieve=extend_schema(tags=["Catalog"], summary="Get product by slug"),
)
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ["name", "description", "brand__name"]
    ordering_fields = ["name", "created_at", "updated_at", "variants__price"]

    def get_queryset(self):
        return (
            Product.objects.filter(is_active=True)
            .select_related("brand", "subcategory", "subcategory__category")
            .prefetch_related("images", "variants", "variants__discount")
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductListSerializer


@extend_schema_view(
    list=extend_schema(tags=["Catalog"], summary="List product variants"),
    retrieve=extend_schema(tags=["Catalog"], summary="Get variant by id"),
)
class ProductVariantViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductVariantSerializer

    def get_queryset(self):
        return (
            ProductVariant.objects.filter(is_active=True)
            .select_related("product", "product__brand", "product__subcategory", "product__subcategory__category")
            .select_related("discount")
            .order_by("product__name", "name")
        )
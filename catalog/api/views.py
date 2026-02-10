from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema, extend_schema_view

from catalog.models import Category, SubCategory
from .serializers import (
    CategoryListSerializer,
    CategoryDetailSerializer,
    SubCategorySerializer,
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

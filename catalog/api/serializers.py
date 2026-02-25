from rest_framework import serializers
from catalog.models import Category, SubCategory, Brand, Product, ProductVariant, Discount, ProductImage
from django.utils import timezone
from decimal import Decimal


class SubCategorySerializer(serializers.ModelSerializer):
    category_slug = serializers.CharField(source="category.slug", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = SubCategory
        fields = [
            "id",
            "category",
            "category_slug",
            "category_name",
            "name",
            "slug",
            "is_active",
            "order",
        ]


class CategoryListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon", "is_active", "order"]


class CategoryDetailSerializer(serializers.ModelSerializer):
    subcategories = SubCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon", "is_active", "order", "subcategories"]



class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "slug", "logo"]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "is_main"]


class DiscountSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Discount
        fields = ["percent", "start_date", "end_date", "is_active", "is_valid"]


class ProductVariantSerializer(serializers.ModelSerializer):
    is_in_stock = serializers.BooleanField(read_only=True)
    discount = DiscountSerializer(read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "product",
            "name",
            "unit",
            "value",
            "price",
            "stock_quantity",
            "sku",
            "is_active",
            "updated_at",
            "is_in_stock",
            "discount",
        ]


class ProductListSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)
    subcategory_slug = serializers.CharField(
        source="subcategory.slug",
        read_only=True
    )
    category_slug = serializers.CharField(
        source="subcategory.category.slug",
        read_only=True
    )
    main_image = serializers.SerializerMethodField(read_only=True)
    min_price = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "is_featured",
            "brand",
            "subcategory_slug",
            "category_slug",
            "main_image",
            "min_price",
        ]

    def get_main_image(self, obj) -> str | None:
        img = next((i for i in obj.images.all() if i.is_main), None)
        return img.image.url if img and img.image else None

    def get_min_price(self, obj) -> Decimal | None:
        prices = [v.price for v in obj.variants.all() if v.is_active]
        return min(prices) if prices else None


class ProductDetailSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)

    subcategory = serializers.SlugRelatedField(
        slug_field="slug", read_only=True
    )
    category = serializers.CharField(source="subcategory.category.slug", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "is_featured",
            "created_at",
            "updated_at",
            "brand",
            "subcategory",
            "category",
            "images",
            "variants",
        ]







from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    SubCategoryViewSet,
    BrandViewSet,
    ProductViewSet,
    ProductVariantViewSet,
)

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="catalog-categories")
router.register(r"subcategories", SubCategoryViewSet, basename="catalog-subcategories")
router.register(r"brands", BrandViewSet, basename="catalog-brands")
router.register(r"products", ProductViewSet, basename="catalog-products")
router.register(r"variants", ProductVariantViewSet, basename="catalog-variants")

urlpatterns = router.urls 

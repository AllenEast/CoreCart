from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, SubCategoryViewSet

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="catalog-categories")
router.register(r"subcategories", SubCategoryViewSet, basename="catalog-subcategories")

urlpatterns = router.urls

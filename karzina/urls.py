import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path("admin/", admin.site.urls),

    path("api/schema/", SpectacularAPIView.as_view(api_version="v1"), name="schema"),

    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    path("api/cart/", include("cart.api.urls")),
    path("api/catalog/", include("catalog.api.urls")),
    path("api/orders/", include("orders.api.urls")),
    path("api/users/", include("users.api.urls")),
    path("api/payments/", include("payments.api.urls")),
    path("api/chat/", include("chat.api.urls")),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]

if settings.DEBUG or os.getenv("DJANGO_SERVE_MEDIA", "1") == "1":
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG or os.getenv("DJANGO_SERVE_STATIC", "1") == "1":
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)



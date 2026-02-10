from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

@extend_schema(
    tags=["Cart"],
    summary="Cart service health",
    responses={200: dict},
)
@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "service": "cart"})

@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "service": "cart"})

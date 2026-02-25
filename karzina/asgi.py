import os

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    os.getenv("DJANGO_SETTINGS_MODULE", "karzina.settings.prod"),
)

from django.core.asgi import get_asgi_application

# ✅ Django'ni avval to'liq ishga tushirib olamiz (AppRegistry ready bo'ladi)
django_asgi_app = get_asgi_application()

# ✅ Shundan keyin Channels va chat importlar
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

from chat.middleware import JwtAuthMiddlewareStack
from chat.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            JwtAuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        ),
    }
)
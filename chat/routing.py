from django.urls import re_path
from .consumers import ChatGatewayConsumer

websocket_urlpatterns = [
    re_path(r"ws/chat/$", ChatGatewayConsumer.as_asgi()),
    re_path(
        r"ws/chat/conversations/(?P<conversation_id>\d+)/$",
        ChatGatewayConsumer.as_asgi(),
    ),
]

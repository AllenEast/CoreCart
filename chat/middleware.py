from __future__ import annotations

from urllib.parse import parse_qs
from typing import Optional

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model

from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

def _extract_bearer(auth_header_value: str) -> Optional[str]:
    if not auth_header_value:
        return None
    parts = auth_header_value.strip().split()
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _get_header(scope, header_name: bytes) -> Optional[str]:
    for k, v in scope.get("headers", []):
        if k.lower() == header_name.lower():
            try:
                return v.decode("utf-8")
            except Exception:
                return None
    return None


@database_sync_to_async
def get_user(token: str):

    try:
        access = AccessToken(token)
        user_id = access.get("user_id")
        if not user_id:
            return AnonymousUser()
        user = User.objects.get(id=user_id)
        if hasattr(user, 'is_active') and not user.is_active:
            return AnonymousUser()
        return user
    except Exception:
        return AnonymousUser()

class JwtAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        auth = _get_header(scope, b"authorization")
        token = _extract_bearer(auth or "")

        if not token:
            query = parse_qs(scope.get("query_string", b"").decode("utf-8", errors="ignore"))
            token = (query.get("token") or [None])[0]

        scope["user"] = await get_user(token) if token else AnonymousUser()
        return await self.app(scope, receive, send)

def JwtAuthMiddlewareStack(inner):
    return JwtAuthMiddleware(inner)

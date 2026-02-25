import json
from collections import deque
from typing import Any, Dict, List, Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache

from chat.models import Conversation, ConversationMember, Message, Attachment
MAX_MESSAGE_LEN = 2000
MAX_MESSAGES_PER_10S = 25
MAX_TYPING_EVENTS_PER_10S = 40


def _user_group(user_id: int) -> str:
    return f"user_{user_id}"


def _conv_group(conversation_id: int) -> str:
    return f"conv_{conversation_id}"


def _throttle_key(user_id: int, kind: str) -> str:
    return f"chatv2:u:{user_id}:throttle:{kind}"


@database_sync_to_async
def throttle_hit(user_id: int, kind: str, limit: int, window_sec: int) -> bool:
    key = _throttle_key(user_id, kind)
    try:
        current = cache.get(key)
        if current is None:
            cache.set(key, 1, timeout=window_sec)
            return False
        current = int(current) + 1
        cache.set(key, current, timeout=window_sec)
        return current > limit
    except Exception:
        return False


@database_sync_to_async
def is_member(conversation_id: int, user_id: int) -> bool:
    return ConversationMember.objects.filter(conversation_id=conversation_id, user_id=user_id).exists()


@database_sync_to_async
def save_message(conversation_id: int, sender_id: int, text: str, attachment_id: int | None = None) -> Message:
    attachment = None
    if attachment_id:
        try:
            attachment = Attachment.objects.get(id=attachment_id)
        except Attachment.DoesNotExist:
            attachment = None
    msg = Message.objects.create(conversation_id=conversation_id, sender_id=sender_id, text=text, attachment=attachment)
    ConversationMember.objects.filter(conversation_id=conversation_id, user_id=sender_id).update(last_read_message=msg)
    return msg


@database_sync_to_async
def fetch_messages(conversation_id: int, before_id: Optional[int], limit: int = 30) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 30), 100))
    qs = Message.objects.filter(conversation_id=conversation_id).order_by("-id")
    if before_id:
        qs = qs.filter(id__lt=int(before_id))
    items = list(qs[:limit])
    items.reverse()

    return [
        {
            "id": m.id,
            "conversation_id": conversation_id,
            "sender_id": m.sender_id,
            "text": "" if getattr(m, "is_deleted", False) else (m.text or ""),
            "is_deleted": bool(getattr(m, "is_deleted", False)),
            "created_at": m.created_at.isoformat(),
        }
        for m in items
    ]


@database_sync_to_async
def attachment_payload(attachment_id: int | None) -> dict | None:
    if not attachment_id:
        return None
    try:
        a = Attachment.objects.get(id=attachment_id)
    except Attachment.DoesNotExist:
        return None
    return {
        "id": a.id,
        "url": a.file.url if a.file else None,
        "original_name": a.original_name,
        "mime_type": a.mime_type,
        "size":  a.size,
        "created_at": a.created_at.isoformat(),
    }


@database_sync_to_async
def mark_delivered(conversation_id: int, user_id: int, up_to_id: int) -> Optional[int]:
    member = ConversationMember.objects.filter(conversation_id=conversation_id, user_id=user_id).first()
    if not member:
        return None
    msg = Message.objects.filter(conversation_id=conversation_id, id=up_to_id).first()
    if not msg:
        return None
    # Only move forward
    if member.last_delivered_message_id and member.last_delivered_message_id >= msg.id:
        return member.last_delivered_message_id
    member.last_delivered_message = msg
    member.save(update_fields=["last_delivered_message"])
    return msg.id


@database_sync_to_async
def mark_read(conversation_id: int, user_id: int, up_to_id: int) -> Optional[int]:
    member = ConversationMember.objects.filter(conversation_id=conversation_id, user_id=user_id).first()
    if not member:
        return None
    msg = Message.objects.filter(conversation_id=conversation_id, id=up_to_id).first()
    if not msg:
        return None
    if member.last_read_message_id and member.last_read_message_id >= msg.id:
        return member.last_read_message_id
    member.last_read_message = msg
    member.save(update_fields=["last_read_message"])
    return msg.id


class ChatGatewayConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user_id = int(user.id)
        self.user_group = _user_group(self.user_id)
        self.joined_conversations = set()
        self._seen_message_ids = deque(maxlen=500)

        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()
        cid = (self.scope.get("url_route", {}) or {}).get("kwargs", {}).get("conversation_id")
        if cid:
            try:
                cid_int = int(cid)
                if await is_member(cid_int, self.user_id):
                    await self.channel_layer.group_add(_conv_group(cid_int), self.channel_name)
                    self.joined_conversations.add(cid_int)
            except Exception:
                pass

        await self.send(text_data=json.dumps({"type": "hello", "user_id": self.user_id}))


    async def disconnect(self, code):
        try:
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
        except Exception:
            pass
        for cid in list(self.joined_conversations):
            try:
                await self.channel_layer.group_discard(_conv_group(cid), self.channel_name)
            except Exception:
                pass


    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser):
            return

        try:
            payload = json.loads(text_data)
        except Exception:
            await self.send(text_data=json.dumps({"type": "error", "code": "bad_json"}))
            return

        msg_type = (payload.get("type") or "").strip().lower()
        conversation_id = payload.get("conversation_id")

        if msg_type in {"join", "leave", "message", "typing", "read", "fetch"}:
            if not conversation_id:
                await self.send(text_data=json.dumps({"type": "error", "code": "conversation_id_required"}))
                return
            try:
                conversation_id = int(conversation_id)
            except Exception:
                await self.send(text_data=json.dumps({"type": "error", "code": "bad_conversation_id"}))
                return

            if not await is_member(conversation_id, self.user_id):
                await self.send(text_data=json.dumps({"type": "error", "code": "forbidden"}))
                return

        if msg_type == "join":
            group = _conv_group(conversation_id)
            await self.channel_layer.group_add(group, self.channel_name)
            self.joined_conversations.add(conversation_id)
            await self.send(text_data=json.dumps({"type": "joined", "conversation_id": conversation_id}))
            return

        if msg_type == "leave":
            group = _conv_group(conversation_id)
            try:
                await self.channel_layer.group_discard(group, self.channel_name)
            except Exception:
                pass
            self.joined_conversations.discard(conversation_id)
            await self.send(text_data=json.dumps({"type": "left", "conversation_id": conversation_id}))
            return

        if msg_type == "message":
            if await throttle_hit(self.user_id, "msg", MAX_MESSAGES_PER_10S, 10):
                await self.send(text_data=json.dumps({"type": "error", "code": "rate_limited"}))
                return

            text = (payload.get("text") or "").strip()
            attachment_id = payload.get("attachment_id")
            try:
                attachment_id_int = int(attachment_id) if attachment_id is not None else None
            except (TypeError, ValueError):
                attachment_id_int = None

            if not text and not attachment_id_int:
                return
            if text and len(text) > MAX_MESSAGE_LEN:
                await self.send(text_data=json.dumps({"type": "error", "code": "message_too_long"}))
                return

            msg = await save_message(conversation_id, self.user_id, text, attachment_id_int)
            event = {
                "type": "chat.message",
                "message": {
                    "type": "message",
                    "id": msg.id,
                    "conversation_id": conversation_id,
                    "sender_id": self.user_id,
                    "text": msg.text,
                    "attachment": await attachment_payload(msg.attachment_id),
                    "created_at": msg.created_at.isoformat(),
                },
            }
            await self.channel_layer.group_send(_conv_group(conversation_id), event)
            await self.channel_layer.group_send(self.user_group, event)

            other_ids = await database_sync_to_async(list)(
                ConversationMember.objects.filter(conversation_id=conversation_id)
                .exclude(user_id=self.user_id)
                .values_list("user_id", flat=True)
            )
            for uid in other_ids:
                await self.channel_layer.group_send(_user_group(int(uid)), event)
            return

        if msg_type == "typing":
            if await throttle_hit(self.user_id, "typing", MAX_TYPING_EVENTS_PER_10S, 10):
                return
            is_typing = bool(payload.get("is_typing"))
            await self.channel_layer.group_send(
                _conv_group(conversation_id),
                {
                    "type": "chat.typing",
                    "conversation_id": conversation_id,
                    "user_id": self.user_id,
                    "is_typing": is_typing,
                },
            )
            return

        if msg_type == "read":
            up_to_id = payload.get("up_to_id")
            if not up_to_id:
                return
            try:
                up_to_id = int(up_to_id)
            except Exception:
                return
            last = await mark_read(conversation_id, self.user_id, up_to_id)
            if not last:
                return
            await self.channel_layer.group_send(
                _conv_group(conversation_id),
                {
                    "type": "chat.read",
                    "conversation_id": conversation_id,
                    "user_id": self.user_id,
                    "up_to_id": int(last),
                },
            )
            return

        if msg_type == "fetch":
            before_id = payload.get("before_id")
            limit = payload.get("limit", 30)
            items = await fetch_messages(conversation_id, before_id=before_id, limit=limit)
            await self.send(text_data=json.dumps({"type": "messages", "conversation_id": conversation_id, "items": items}))
            return


    async def chat_message(self, event):
        msg = event.get("message") or {}
        # Per-connection de-duplication (message may arrive via both user_group and conv_group)
        try:
            mid = int(msg.get("id") or 0)
        except Exception:
            mid = 0
        if mid and mid in self._seen_message_ids:
            return
        if mid:
            self._seen_message_ids.append(mid)

        await self.send(text_data=json.dumps(msg))


        try:
            conversation_id = int(msg.get("conversation_id") or 0)
            message_id = int(msg.get("id") or 0)
            sender_id = int(msg.get("sender_id") or 0)
        except Exception:
            return

        if conversation_id and message_id and sender_id and sender_id != getattr(self, "user_id", None):
            last = await mark_delivered(conversation_id, self.user_id, message_id)
            if last:
                await self.channel_layer.group_send(
                    _conv_group(conversation_id),
                    {
                        "type": "chat.delivered",
                        "conversation_id": conversation_id,
                        "user_id": self.user_id,
                        "up_to_id": int(last),
                    },
                )

    async def chat_typing(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "conversation_id": event.get("conversation_id"),
                    "user_id": event.get("user_id"),
                    "is_typing": bool(event.get("is_typing")),
                }
            )
        )

    async def chat_read(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "read",
                    "conversation_id": event.get("conversation_id"),
                    "user_id": event.get("user_id"),
                    "up_to_id": event.get("up_to_id"),
                }
            )
        )


    async def chat_delivered(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "delivered",
                    "conversation_id": event.get("conversation_id"),
                    "user_id": event.get("user_id"),
                    "up_to_id": event.get("up_to_id"),
                }
            )
        )


    async def chat_message_deleted(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_deleted",
                    "conversation_id": event.get("conversation_id"),
                    "message_id": event.get("message_id"),
                    "deleted_by": event.get("deleted_by"),
                }
            )
        )

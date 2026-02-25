from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

from rest_framework import permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from chat.models import Attachment, Conversation, ConversationMember, Message, SupportAssignmentState, MessageReport
from .serializers import (
    ConversationCreateSerializer,
    ConversationListSerializer,
    MessageSerializer,
    AttachmentSerializer,
    EmptySerializer,
    ReasonSerializer,
    MarkReadRequestSerializer,
    SupportAutoAssignRequestSerializer,
)


User = get_user_model()




class IsOperator(permissions.BasePermission):
    """Allow only operators/staff to access support queue endpoints."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, "is_operator", False))


class DefaultPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100


def _conv_group(conv_id: int) -> str:
    return f"conv_{conv_id}"


def _user_group(user_id: int) -> str:
    return f"user_{user_id}"


def _push_message_event(message: Message) -> None:
    """Push message to websocket groups (conversation + each participant user group)."""
    channel_layer = get_channel_layer()
    payload = {
        "type": "chat.message",
        "message": {
            "type": "message",
            "id": message.id,
            "conversation_id": message.conversation_id,
            "sender_id": message.sender_id,
            "text": "" if getattr(message, "is_deleted", False) else (message.text or ""),
            "is_deleted": bool(getattr(message, "is_deleted", False)),
            "attachment": (
                {
                    "id": message.attachment_id,
                    "url": message.attachment.file.url if message.attachment and message.attachment.file else None,
                    "thumbnail_url": message.attachment.thumbnail.url if message.attachment and getattr(message.attachment, "thumbnail", None) else None,
                    "original_name": message.attachment.original_name if message.attachment else "",
                    "mime_type": message.attachment.mime_type if message.attachment else "",
                    "size": message.attachment.size if message.attachment else 0,
                }
                if message.attachment_id
                else None
            ),
            "created_at": message.created_at.isoformat(),
        },
    }
    # 1) conversation group
    async_to_sync(channel_layer.group_send)(_conv_group(message.conversation_id), payload)

    # 2) per-user inbox group (so people who didn't "join" still get notified)
    member_ids = list(
        ConversationMember.objects.filter(conversation_id=message.conversation_id)
        .values_list("user_id", flat=True)
    )
    for uid in member_ids:
        async_to_sync(channel_layer.group_send)(_user_group(uid), payload)




def _pick_operator_round_robin() -> User | None:
    """
    Pick next operator in round-robin order.
    - Primary pool: role="operator", is_active=True
    - Fallback: is_staff=True, is_active=True
    """
    ops = list(User.objects.filter(is_active=True, role="operator").order_by("id").only("id"))
    if not ops:
        ops = list(User.objects.filter(is_active=True, is_staff=True).order_by("id").only("id"))
    if not ops:
        return None

    with transaction.atomic():
        state, _ = SupportAssignmentState.objects.select_for_update().get_or_create(id=1)
        ids = [o.id for o in ops]
        if state.last_operator_id in ids:
            i = ids.index(state.last_operator_id)
            chosen_id = ids[(i + 1) % len(ids)]
        else:
            chosen_id = ids[0]
        state.last_operator_id = chosen_id
        state.save(update_fields=["last_operator", "updated_at"])
    return User.objects.filter(id=chosen_id).first()

class ConversationListCreateApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationCreateSerializer

    def get(self, request):
        user = request.user
        q = (request.query_params.get("q") or "").strip()

        last_msg_qs = Message.objects.filter(conversation_id=OuterRef("pk")).order_by("-id")

        qs = (
            Conversation.objects.filter(members__user=user)
            .prefetch_related("members__user")
            .annotate(
                last_message_id=Subquery(last_msg_qs.values("id")[:1]),
                last_message_text=Subquery(last_msg_qs.values("text")[:1]),
                last_message_sender=Subquery(last_msg_qs.values("sender_id")[:1]),
                last_message_time=Subquery(last_msg_qs.values("created_at")[:1]),
            )
            .order_by("-last_message_time", "-created_at")
        )

        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(members__user__username__icontains=q)
                | Q(members__user__first_name__icontains=q)
                | Q(members__user__last_name__icontains=q)
            ).distinct()

        convs = list(qs)
        # preload last messages
        last_ids = [c.last_message_id for c in convs if c.last_message_id]
        last_map = {m.id: m for m in Message.objects.filter(id__in=last_ids)}
        for c in convs:
            c._last_message_obj = last_map.get(getattr(c, "last_message_id", None))

        # compute unread
        member_map = {
            m.conversation_id: m
            for m in ConversationMember.objects.filter(user=user, conversation_id__in=[c.id for c in convs]).select_related(
                "last_read_message"
            )
        }
        for c in convs:
            me = member_map.get(c.id)
            last_read_id = me.last_read_message_id if me else None
            unread_q = Message.objects.filter(conversation=c).exclude(sender=user)
            if last_read_id:
                unread_q = unread_q.filter(id__gt=last_read_id)
            c.unread_count = unread_q.count()

        data = ConversationListSerializer(convs, many=True, context={"request": request}).data
        return Response(data)

    def post(self, request):
        ser = ConversationCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user: User = request.user

        support = bool(ser.validated_data.get("support"))
        other_user_id = ser.validated_data.get("user_id")
        participant_ids = ser.validated_data.get("participant_ids") or []
        title = (ser.validated_data.get("title") or "").strip()

        if support:
            return self._create_support(request)

        if other_user_id:
            return self._create_direct(request, other_user_id)

        return self._create_group(request, participant_ids, title)

    def _create_direct(self, request, other_user_id: int):
        user = request.user
        if int(other_user_id) == user.id:
            return Response({"detail": "O'zingiz bilan chat yo'q"}, status=400)

        other = User.objects.filter(id=other_user_id).first()
        if not other:
            return Response({"detail": "User topilmadi"}, status=404)

        qs = (
            Conversation.objects.filter(type=Conversation.Type.DIRECT)
            .filter(members__user=user)
            .filter(members__user=other)
            .annotate(member_count=Count("members"))
            .filter(member_count=2)
        )
        conv = qs.first()
        if conv:
            return Response({"id": conv.id}, status=200)

        with transaction.atomic():
            conv = Conversation.objects.create(type=Conversation.Type.DIRECT, created_by=user)
            ConversationMember.objects.create(conversation=conv, user=user, role=ConversationMember.Role.USER)
            ConversationMember.objects.create(conversation=conv, user=other, role=ConversationMember.Role.USER)

        return Response({"id": conv.id}, status=201)

    def _create_support(self, request):
        user = request.user

        # Existing support chat?
        qs = (
            Conversation.objects.filter(type=Conversation.Type.SUPPORT)
            .filter(members__user=user)
            .annotate(member_count=Count("members"))
            .filter(member_count=2)
        )
        conv = qs.first()
        if conv:
            return Response({"id": conv.id}, status=200)

        # Pick operator in round-robin order (production-friendly)
        staff = _pick_operator_round_robin()
        if not staff:
            return Response({"detail": "Support/Operator topilmadi"}, status=500)

        if staff.id == user.id:
            return Response({"detail": "O'zingiz support bo'lib o'zingiz bilan chat yo'q"}, status=400)

        with transaction.atomic():
            conv = Conversation.objects.create(type=Conversation.Type.SUPPORT, created_by=user, assigned_to=staff)
            ConversationMember.objects.create(conversation=conv, user=user, role=ConversationMember.Role.USER)
            ConversationMember.objects.create(conversation=conv, user=staff, role=ConversationMember.Role.SUPPORT)

        return Response({"id": conv.id}, status=201)

    def _create_group(self, request, participant_ids: list[int], title: str):
        user = request.user
        ids = set(int(i) for i in participant_ids)
        ids.add(user.id)
        users = list(User.objects.filter(id__in=list(ids), is_active=True))
        if len(users) < 2:
            return Response({"detail": "Participantlar topilmadi"}, status=400)

        with transaction.atomic():
            conv = Conversation.objects.create(
                type=Conversation.Type.GROUP,
                title=title,
                created_by=user,
            )
            ConversationMember.objects.bulk_create(
                [ConversationMember(conversation=conv, user=u, role=ConversationMember.Role.USER) for u in users]
            )

        return Response({"id": conv.id}, status=201)


class MessageListCreateApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MessageSerializer
    pagination_class = DefaultPagination

    def get(self, request, conversation_id: int):
        user = request.user
        if not ConversationMember.objects.filter(conversation_id=conversation_id, user=user).exists():
            return Response({"detail": "Ruxsat yo'q"}, status=403)

        qs = Message.objects.filter(conversation_id=conversation_id).select_related("sender").order_by("-id")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        data = MessageSerializer(page, many=True, context={"request": request}).data

        # Delivery/read receipts (counts) - computed for this page only (safe & fast for small pages)
        member_states = list(
            ConversationMember.objects.filter(conversation_id=conversation_id)
            .values("user_id", "last_delivered_message_id", "last_read_message_id")
        )
        for item in data:
            mid = int(item["id"])
            delivered = 0
            read = 0
            for st in member_states:
                if st["user_id"] == request.user.id:
                    continue
                if st["last_delivered_message_id"] and st["last_delivered_message_id"] >= mid:
                    delivered += 1
                if st["last_read_message_id"] and st["last_read_message_id"] >= mid:
                    read += 1
            item["delivered_count"] = delivered
            item["read_count"] = read

        return paginator.get_paginated_response(data)

    def post(self, request, conversation_id: int):
        user = request.user
        if not ConversationMember.objects.filter(conversation_id=conversation_id, user=user).exists():
            return Response({"detail": "Ruxsat yo'q"}, status=403)

        text = (request.data.get("text") or "").strip()
        attachment_id = request.data.get("attachment_id")
        attachment = None

        if attachment_id:
            try:
                attachment = Attachment.objects.get(id=int(attachment_id))
            except (Attachment.DoesNotExist, ValueError, TypeError):
                return Response({"detail": "attachment_id noto'g'ri"}, status=400)
            # Optional: only allow using own uploaded attachments unless operator
            if attachment.uploader_id and attachment.uploader_id != user.id and not getattr(user, "is_operator", False):
                return Response({"detail": "attachment uchun ruxsat yo'q"}, status=403)

        if not text and not attachment:
            return Response({"detail": "text yoki attachment_id majburiy"}, status=400)
        if text and len(text) > 2000:
            return Response({"detail": "text juda uzun"}, status=400)

        msg = Message.objects.create(conversation_id=conversation_id, sender=user, text=text, attachment=attachment)

        # Sender has read up to their own message.
        ConversationMember.objects.filter(conversation_id=conversation_id, user=user).update(last_read_message=msg)

        msg = Message.objects.select_related("attachment").get(id=msg.id)
        _push_message_event(msg)
        return Response(MessageSerializer(msg, context={"request": request}).data, status=201)


class AttachmentUploadApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AttachmentSerializer

    def post(self, request):
        f = request.FILES.get("file")
        if not f:
            return Response({"detail": "file majburiy"}, status=400)
        if f.size > 20 * 1024 * 1024:
            return Response({"detail": "file juda katta (max 20MB)"}, status=400)

        att = Attachment.objects.create(
            uploader=request.user,
            file=f,
            original_name=getattr(f, "name", ""),
            mime_type=getattr(f, "content_type", "") or "",
            size=getattr(f, "size", 0) or 0,
        )

        # Thumbnail for images (best-effort)
        try:
            if (att.mime_type or "").startswith("image/") and att.file:
                img = Image.open(att.file)
                img = img.convert("RGB")
                img.thumbnail((480, 480))
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=85)
                buf.seek(0)
                thumb_name = f"thumb_{att.id}.jpg"
                att.thumbnail.save(thumb_name, ContentFile(buf.read()), save=True)
        except Exception:
            # Don't fail upload if thumbnail generation fails
            pass

        data = AttachmentSerializer(att, context={"request": request}).data
        return Response(data, status=201)


class SupportQueueListApiView(APIView):
    """Operator dashboard uchun support queue."""

    permission_classes = [permissions.IsAuthenticated, IsOperator]
    @extend_schema(summary="List support queue", responses={200: OpenApiTypes.OBJECT})

    def get(self, request):
        qs = (
            Conversation.objects.filter(type=Conversation.Type.SUPPORT)
            .select_related("assigned_to")
            .order_by("status", "-created_at")
        )

        # filters
        status_f = request.query_params.get("status")
        if status_f in [Conversation.Status.OPEN, Conversation.Status.CLOSED]:
            qs = qs.filter(status=status_f)

        assigned = request.query_params.get("assigned")
        if assigned == "me":
            qs = qs.filter(assigned_to=request.user)
        elif assigned == "unassigned":
            qs = qs.filter(assigned_to__isnull=True)

        # annotate last message
        last_msg = Message.objects.filter(conversation_id=OuterRef("pk")).order_by("-id")
        qs = qs.annotate(last_message_id=Subquery(last_msg.values("id")[:1]))

        data = ConversationListSerializer(qs, many=True, context={"request": request}).data
        return Response(data)


class SupportAssignApiView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOperator]
    serializer_class = EmptySerializer

    @transaction.atomic
    @extend_schema(summary="Assign conversation to operator", request=None, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, conversation_id: int):
        try:
            conv = Conversation.objects.select_for_update().get(id=conversation_id, type=Conversation.Type.SUPPORT)
        except Conversation.DoesNotExist:
            return Response({"detail": "Conversation topilmadi"}, status=404)

        if conv.status != Conversation.Status.OPEN:
            return Response({"detail": "Conversation yopilgan"}, status=400)

        # Assign to me
        conv.assigned_to = request.user
        conv.save(update_fields=["assigned_to"])
        return Response({"id": conv.id, "assigned_to": request.user.id})


class SupportCloseApiView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOperator]
    serializer_class = EmptySerializer

    @transaction.atomic
    @extend_schema(summary="Close support conversation", request=None, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, conversation_id: int):
        try:
            conv = Conversation.objects.select_for_update().get(id=conversation_id, type=Conversation.Type.SUPPORT)
        except Conversation.DoesNotExist:
            return Response({"detail": "Conversation topilmadi"}, status=404)

        conv.status = Conversation.Status.CLOSED
        conv.save(update_fields=["status"])
        return Response({"id": conv.id, "status": conv.status})


class MarkReadApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MarkReadRequestSerializer
    @extend_schema(summary="Mark messages as read", request=MarkReadRequestSerializer, responses={200: OpenApiTypes.OBJECT})

    def post(self, request, conversation_id: int):
        user = request.user
        up_to_id = request.data.get("up_to_id")
        if not up_to_id:
            return Response({"detail": "up_to_id majburiy"}, status=400)

        member = ConversationMember.objects.filter(conversation_id=conversation_id, user=user).select_related(
            "last_read_message"
        ).first()
        if not member:
            return Response({"detail": "Ruxsat yo'q"}, status=403)

        msg = Message.objects.filter(conversation_id=conversation_id, id=int(up_to_id)).first()
        if not msg:
            return Response({"detail": "Message topilmadi"}, status=404)

        # Only move forward
        if member.last_read_message_id and member.last_read_message_id >= msg.id:
            return Response({"ok": True, "last_read": member.last_read_message_id})

        member.last_read_message = msg
        member.save(update_fields=["last_read_message"])

        # optional WS event
        channel_layer = get_channel_layer()
        payload = {
            "type": "chat.read",
            "conversation_id": conversation_id,
            "user_id": user.id,
            "up_to_id": msg.id,
        }
        async_to_sync(channel_layer.group_send)(_conv_group(conversation_id), payload)
        async_to_sync(channel_layer.group_send)(_user_group(user.id), payload)

        return Response({"ok": True, "last_read": msg.id})


class UnreadSummaryApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmptySerializer
    @extend_schema(summary="Unread summary", responses={200: OpenApiTypes.OBJECT})

    def get(self, request):
        user = request.user
        conv_ids = list(ConversationMember.objects.filter(user=user).values_list("conversation_id", flat=True))
        if not conv_ids:
            return Response({"has_unread": False})

        members = {
            m.conversation_id: m.last_read_message_id
            for m in ConversationMember.objects.filter(user=user, conversation_id__in=conv_ids)
        }
        for cid in conv_ids:
            last_read = members.get(cid)
            q = Message.objects.filter(conversation_id=cid).exclude(sender=user)
            if last_read:
                q = q.filter(id__gt=last_read)
            if q.exists():
                return Response({"has_unread": True})
        return Response({"has_unread": False})


class SupportAutoAssignApiView(APIView):
    """
    Assign unassigned OPEN support conversations to operators in round-robin order.
    POST body: {"limit": 20} (optional)
    """
    permission_classes = [permissions.IsAuthenticated, IsOperator]
    @extend_schema(summary="Auto-assign support conversations", request=SupportAutoAssignRequestSerializer, responses={200: OpenApiTypes.OBJECT})

    def post(self, request):
        limit = int(request.data.get("limit") or 20)
        limit = max(1, min(limit, 200))

        assigned = 0
        conv_ids = list(
            Conversation.objects.filter(type=Conversation.Type.SUPPORT, status=Conversation.Status.OPEN, assigned_to__isnull=True)
            .order_by("created_at")
            .values_list("id", flat=True)[:limit]
        )
        for cid in conv_ids:
            staff = _pick_operator_round_robin()
            if not staff:
                break
            with transaction.atomic():
                conv = Conversation.objects.select_for_update().filter(id=cid, assigned_to__isnull=True).first()
                if not conv:
                    continue
                conv.assigned_to = staff
                conv.save(update_fields=["assigned_to"])
                # ensure operator is a member
                ConversationMember.objects.get_or_create(
                    conversation=conv,
                    user=staff,
                    defaults={"role": ConversationMember.Role.SUPPORT},
                )
            assigned += 1

        return Response({"assigned": assigned})


class ConversationSearchApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmptySerializer
    @extend_schema(summary="Search conversations", parameters=[OpenApiParameter(name="q", type=OpenApiTypes.STR, required=True)], responses={200: OpenApiTypes.OBJECT})

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if not q:
            return Response({"results": []})

        user = request.user
        qs = (
            Conversation.objects.filter(members__user=user)
            .filter(
                Q(title__icontains=q)
                | Q(members__user__username__icontains=q)
                | Q(members__user__first_name__icontains=q)
                | Q(members__user__last_name__icontains=q)
            )
            .distinct()
            .order_by("-created_at")[:50]
        )
        data = ConversationListSerializer(qs, many=True, context={"request": request}).data
        return Response({"results": data})


class MessageSearchApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmptySerializer
    @extend_schema(summary="Search messages", parameters=[OpenApiParameter(name="q", type=OpenApiTypes.STR, required=True), OpenApiParameter(name="conversation_id", type=OpenApiTypes.INT, required=False)], responses={200: OpenApiTypes.OBJECT})

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        conversation_id = request.query_params.get("conversation_id")
        if not q:
            return Response({"results": []})

        qs = Message.objects.filter(is_deleted=False).select_related("sender", "attachment")
        if conversation_id:
            qs = qs.filter(conversation_id=int(conversation_id))
        # must be member for each conversation; if conversation_id provided, enforce membership
        if conversation_id:
            if not ConversationMember.objects.filter(conversation_id=int(conversation_id), user=request.user).exists():
                return Response({"detail": "forbidden"}, status=403)
        else:
            qs = qs.filter(conversation__members__user=request.user)

        qs = qs.filter(text__icontains=q).order_by("-id")[:50]
        data = MessageSerializer(qs, many=True, context={"request": request}).data
        return Response({"results": data})


class MessageDeleteApiView(APIView):
    """
    Soft-delete a message.
    - Sender can delete their own message
    - Operator/admin can delete messages in conversations they are a member of
    POST body: {"reason": "..."} optional
    """
    permission_classes = [permissions.IsAuthenticated]
    @extend_schema(summary="Delete message (soft)", request=ReasonSerializer, responses={200: OpenApiTypes.OBJECT})

    def post(self, request, message_id: int):
        msg = Message.objects.select_related("conversation").filter(id=message_id).first()
        if not msg:
            return Response({"detail": "Not found"}, status=404)

        # must be member
        if not ConversationMember.objects.filter(conversation_id=msg.conversation_id, user=request.user).exists():
            return Response({"detail": "forbidden"}, status=403)

        is_operator = getattr(request.user, "is_operator", False)
        if msg.sender_id != request.user.id and not is_operator:
            return Response({"detail": "forbidden"}, status=403)

        if msg.is_deleted:
            return Response({"ok": True})

        msg.is_deleted = True
        msg.deleted_at = timezone.now()
        msg.deleted_by = request.user
        msg.delete_reason = (request.data.get("reason") or "").strip()
        msg.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "delete_reason"])

        # WS event
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            _conv_group(msg.conversation_id),
            {
                "type": "chat.message_deleted",
                "conversation_id": msg.conversation_id,
                "message_id": msg.id,
                "deleted_by": request.user.id,
            },
        )

        return Response({"ok": True})


class MessageReportApiView(APIView):
    """
    Report a message (for moderation review).
    POST body: {"reason": "..."} optional
    """
    permission_classes = [permissions.IsAuthenticated]
    @extend_schema(summary="Report message", request=ReasonSerializer, responses={201: OpenApiTypes.OBJECT})

    def post(self, request, message_id: int):
        msg = Message.objects.filter(id=message_id).first()
        if not msg:
            return Response({"detail": "Not found"}, status=404)

        if not ConversationMember.objects.filter(conversation_id=msg.conversation_id, user=request.user).exists():
            return Response({"detail": "forbidden"}, status=403)

        reason = (request.data.get("reason") or "").strip()
        MessageReport.objects.create(reporter=request.user, message=msg, reason=reason)
        return Response({"ok": True})

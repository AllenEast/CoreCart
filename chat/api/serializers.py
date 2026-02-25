from django.contrib.auth import get_user_model
from rest_framework import serializers

from chat.models import Attachment, Conversation, ConversationMember, Message


User = get_user_model()

class EmptySerializer(serializers.Serializer):
    """Empty serializer for endpoints without request body."""
    class Meta:
        ref_name = "Empty"

class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
    class Meta:
        ref_name = "Reason"

class MarkReadRequestSerializer(serializers.Serializer):
    up_to_id = serializers.IntegerField(min_value=1)
    class Meta:
        ref_name = "MarkReadRequest"

class SupportAutoAssignRequestSerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=10)
    class Meta:
        ref_name = "SupportAutoAssignRequest"



class UserLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ["id", "url", "thumbnail_url", "original_name", "mime_type", "size", "created_at"]

    def get_url(self, obj):
        request = self.context.get("request")
        if not obj.file:
            return None
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if not getattr(obj, "thumbnail", None):
            return None
        url = obj.thumbnail.url
        return request.build_absolute_uri(url) if request else url


class ConversationMemberSerializer(serializers.ModelSerializer):
    user = UserLiteSerializer(read_only=True)

    class Meta:
        model = ConversationMember
        fields = ["user", "role", "joined_at", "is_muted", "last_read_message"]


class MessageSerializer(serializers.ModelSerializer):
    sender = UserLiteSerializer(read_only=True)
    attachment = AttachmentSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "conversation", "sender", "text", "attachment", "is_system", "created_at", "edited_at", "is_deleted", "deleted_at", "deleted_by", "delete_reason"]
        read_only_fields = ["id", "created_at", "edited_at", "sender", "is_deleted", "deleted_at", "deleted_by", "delete_reason"]



    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Hide text if deleted
        if getattr(instance, "is_deleted", False):
            data["text"] = ""
        return data

class ConversationListSerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()
    assigned_to = UserLiteSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Conversation
        fields = ["id", "type", "title", "status", "assigned_to", "created_at", "members", "last_message", "unread_count"]

    def get_members(self, obj):
        # Expect members prefetched
        return [
            {
                "user": {
                    "id": m.user_id,
                    "username": m.user.username,
                    "first_name": m.user.first_name,
                    "last_name": m.user.last_name,
                },
                "role": m.role,
            }
            for m in getattr(obj, "_prefetched_objects_cache", {}).get("members", obj.members.all())
        ]

    def get_last_message(self, obj):
        lm = getattr(obj, "_last_message_obj", None)
        if lm is None:
            return None
        return {
            "id": lm.id,
            "text": lm.text,
            "sender_id": lm.sender_id,
            "created_at": lm.created_at,
        }


class ConversationCreateSerializer(serializers.Serializer):
    # direct chat
    user_id = serializers.IntegerField(required=False)
    # support chat
    support = serializers.BooleanField(required=False, default=False)
    # group chat
    title = serializers.CharField(required=False, allow_blank=True)
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
    )

    def validate(self, attrs):
        support = bool(attrs.get("support"))
        user_id = attrs.get("user_id")
        participant_ids = attrs.get("participant_ids") or []

        if support:
            return attrs

        if user_id and participant_ids:
            raise serializers.ValidationError("user_id va participant_ids birga bo'lmaydi")

        if user_id:
            return attrs

        if participant_ids:
            if len(set(participant_ids)) < 2:
                raise serializers.ValidationError("Group chat uchun kamida 2 ta participant kerak")
            return attrs

        raise serializers.ValidationError("support=true yoki user_id yoki participant_ids kerak")

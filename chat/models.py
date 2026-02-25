from django.conf import settings
from django.db import models


class Conversation(models.Model):
    class Type(models.TextChoices):
        DIRECT = "direct", "Direct"
        SUPPORT = "support", "Support"
        GROUP = "group", "Group"

    type = models.CharField(max_length=20, choices=Type.choices, db_index=True)
    title = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Support queue fields (used when type=SUPPORT)
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_conversations_v2",
    )

    def __str__(self) -> str:
        return f"Conversation#{self.id} {self.type}"


class Attachment(models.Model):
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_attachments",
    )
    file = models.FileField(upload_to="chat/attachments/%Y/%m/%d/")
    thumbnail = models.ImageField(upload_to="chat/attachments/thumbnails/%Y/%m/%d/", null=True, blank=True)
    original_name = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"Attachment#{self.id} uploader={self.uploader_id}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    attachment = models.ForeignKey(
        Attachment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    text = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Support queue fields (used when type=SUPPORT)
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_chatmessages_v2",
    )
    edited_at = models.DateTimeField(null=True, blank=True)

    # Soft-delete / moderation
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_chat_messages",
    )
    delete_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "id"]),
            models.Index(fields=["conversation", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Message#{self.id} conv={self.conversation_id} sender={self.sender_id}"


class ConversationMember(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        SUPPORT = "support", "Support"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    last_delivered_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    is_muted = models.BooleanField(default=False)

    class Meta:
        unique_together = [("conversation", "user")]
        indexes = [
            models.Index(fields=["user", "conversation"]),
            models.Index(fields=["conversation", "user"]),
        ]

    def __str__(self) -> str:
        return f"Member conv={self.conversation_id} user={self.user_id}"


class SupportAssignmentState(models.Model):
    """Singleton row used to keep round-robin pointer for support assignment."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    last_operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"SupportAssignmentState#{self.id} last={self.last_operator_id}"


class MessageReport(models.Model):
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_reports",
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["message"]),
        ]

    def __str__(self) -> str:
        return f"MessageReport#{self.id} msg={self.message_id} reporter={self.reporter_id}"

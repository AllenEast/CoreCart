from django.urls import path

from .views import (
    ConversationListCreateApiView,
    MarkReadApiView,
    MessageListCreateApiView,
    UnreadSummaryApiView,
    AttachmentUploadApiView,
    SupportAssignApiView,
    SupportCloseApiView,
    SupportQueueListApiView,
    SupportAutoAssignApiView,
    ConversationSearchApiView,
    MessageSearchApiView,
    MessageDeleteApiView,
    MessageReportApiView,
)


urlpatterns = [
    path("conversations/", ConversationListCreateApiView.as_view(), name="chat-conversations"),
    path(
        "conversations/<int:conversation_id>/messages/",
        MessageListCreateApiView.as_view(),
        name="chat-messages",
    ),
    path(
        "conversations/<int:conversation_id>/mark-read/",
        MarkReadApiView.as_view(),
        name="chat-mark-read",
    ),
    path("unread-summary/", UnreadSummaryApiView.as_view(), name="chat-unread-summary"),
    path("upload/", AttachmentUploadApiView.as_view(), name="chat-upload"),
    path("support/queue/", SupportQueueListApiView.as_view(), name="support-queue"),
    path("support/conversations/<int:conversation_id>/assign/", SupportAssignApiView.as_view(), name="support-assign"),
    path("support/conversations/<int:conversation_id>/close/", SupportCloseApiView.as_view(), name="support-close"),
    path("support/auto-assign/", SupportAutoAssignApiView.as_view(), name="support-auto-assign"),
    path("search/conversations/", ConversationSearchApiView.as_view(), name="chat-search-conversations"),
    path("search/messages/", MessageSearchApiView.as_view(), name="chat-search-messages"),
    path("messages/<int:message_id>/delete/", MessageDeleteApiView.as_view(), name="chat-message-delete"),
    path("messages/<int:message_id>/report/", MessageReportApiView.as_view(), name="chat-message-report"),
]

from django.contrib import admin

from .models import (
    Conversation,
    ConversationMember,
    Message,
)



class ConversationMemberInline(admin.TabularInline):
    model = ConversationMember
    extra = 0


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "type", "title", "created_by", "created_at"]
    list_filter = ["type"]
    search_fields = ["title"]
    inlines = [ConversationMemberInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation", "sender", "created_at", "is_system"]
    search_fields = ["text", "sender__username"]
    list_filter = ["is_system"]

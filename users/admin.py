from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    # show role + phone
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Extra", {"fields": ("phone", "address", "role")}),
    )
    list_display = ("username", "phone", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "phone", "email")

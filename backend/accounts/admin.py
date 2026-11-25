from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Division, User

admin.site.register(Division)


@admin.register(User)
class CmsUserAdmin(UserAdmin):
    ordering = ("last_name", "first_name")
    list_display = ("email", "role", "division", "is_active")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("first_name", "last_name", "phone", "role", "division")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "role", "division", "password1", "password2")}),)
    search_fields = ("=email", "first_name", "last_name")

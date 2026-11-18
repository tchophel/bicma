from django.contrib import admin

from .models import AuditLog, Category, Subcategory, SystemConfiguration

admin.site.register([Category, Subcategory, SystemConfiguration])


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    def has_add_permission(self, r): return False
    def has_change_permission(self, r, o=None): return False
    def has_delete_permission(self, r, o=None): return False

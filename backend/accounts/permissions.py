from rest_framework.permissions import BasePermission

from .models import Role


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active and u.base_role == Role.SUPER_ADMIN)


def has_role(user, *roles):
    return bool(user and user.is_authenticated and user.is_active and user.base_role in roles)

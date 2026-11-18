from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("users", views.UserViewSet, basename="admin-user")
router.register("divisions", views.DivisionViewSet, basename="admin-division")

urlpatterns = [
    path("auth/csrf/", views.CsrfView.as_view()),
    path("auth/password-reset/", views.PasswordResetRequestView.as_view()),
    path("auth/password-reset/confirm/", views.PasswordResetConfirmView.as_view()),
    path("auth/ndi/start/", views.NdiStartView.as_view()),
    path("auth/login/", views.LoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/me/", views.MeView.as_view()),
    path("auth/change-password/", views.ChangePasswordView.as_view()),
    path("divisions/", views.DivisionListView.as_view()),
    path("admin/permissions/", views.RolePermissionsView.as_view()),
    path("admin/users/cid-lookup/", views.StaffCidLookupView.as_view()),
    path("admin/divisions/register-focals/", views.RegisterFocalsView.as_view()),
    path("admin/", include(router.urls)),
]

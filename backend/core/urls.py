from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("faqs", views.FAQAdminViewSet, basename="admin-faq")
router.register("categories", views.CategoryAdminViewSet, basename="admin-category")
router.register("subcategories", views.SubcategoryAdminViewSet, basename="admin-subcategory")
router.register("dzongkhags", views.DzongkhagAdminViewSet, basename="admin-dzongkhag")
router.register("gewogs", views.GewogAdminViewSet, basename="admin-gewog")
router.register("audit-logs", views.AuditLogViewSet, basename="admin-audit")

urlpatterns = [
    path("meta/", views.MetaView.as_view()),
    path("notifications/", views.NotificationListView.as_view()),
    path("notifications/read-all/", views.NotificationReadView.as_view()),
    path("notifications/<uuid:pk>/read/", views.NotificationReadView.as_view()),
    path("admin/settings/", views.SettingsView.as_view()),
    path("admin/", include(router.urls)),
]

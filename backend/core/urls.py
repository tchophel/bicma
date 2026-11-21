from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("faqs", views.FAQAdminViewSet, basename="admin-faq")
router.register("categories", views.CategoryAdminViewSet, basename="admin-category")
router.register("subcategories", views.SubcategoryAdminViewSet, basename="admin-subcategory")
router.register("dzongkhags", views.DzongkhagAdminViewSet, basename="admin-dzongkhag")
for _route, _vs in (("provider-types", views.ProviderTypeAdminViewSet), ("providers", views.ProviderAdminViewSet),
                    ("priorities", views.PriorityAdminViewSet), ("outcomes", views.OutcomeAdminViewSet),
                    ("closure-reasons", views.ClosureReasonAdminViewSet), ("holidays", views.HolidayAdminViewSet),
                    ("email-templates", views.EmailTemplateAdminViewSet)):
    router.register(_route, _vs, basename=f"admin-{_route}")
router.register("audit-logs", views.AuditLogViewSet, basename="admin-audit")

urlpatterns = [
    path("meta/", views.MetaView.as_view()),
    path("notifications/", views.NotificationListView.as_view()),
    path("notifications/read-all/", views.NotificationReadView.as_view()),
    path("notifications/<uuid:pk>/read/", views.NotificationReadView.as_view()),
    path("admin/settings/", views.SettingsView.as_view()),
    path("admin/workflow/", views.WorkflowView.as_view()),
    path("admin/logs/<str:kind>/", views.LogListView.as_view()),
    path("admin/api-status/", views.ApiStatusView.as_view()),
    path("admin/", include(router.urls)),
]

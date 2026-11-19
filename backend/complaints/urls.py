from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import dashboard, reports, views

router = DefaultRouter()
router.register("complaints", views.ComplaintViewSet, basename="complaint")

urlpatterns = [
    path("public/complaints/", views.PublicSubmitView.as_view()),
    path("dashboard/", dashboard.DashboardView.as_view()),
    path("public/cid-lookup/", views.PublicCidLookupView.as_view()),
    path("public/captcha/", views.PublicCaptchaView.as_view()),
    path("public/track/", views.PublicTrackView.as_view()),
    path("public/track/reply/", views.PublicReplyView.as_view()),
    path("admin/uploads/", views.AdminUploadsView.as_view()),
    path("reports/", reports.ReportListView.as_view()),
    path("reports/<str:key>/", reports.ReportView.as_view()),
    path("", include(router.urls)),
]

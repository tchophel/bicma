from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import dashboard, reports, views

router = DefaultRouter()
router.register("complaints", views.ComplaintViewSet, basename="complaint")

urlpatterns = [
    path("public/complaints/", views.PublicSubmitView.as_view()),
    path("dashboard/", dashboard.DashboardView.as_view()),
    path("public/cid-lookup/", views.PublicCidLookupView.as_view()),
    path("public/similar/", views.PublicSimilarView.as_view()),
    path("public/stats/", views.PublicStatsView.as_view()),
    path("public/captcha/", views.PublicCaptchaView.as_view()),
    path("public/track/", views.PublicTrackView.as_view()),
    path("public/scan/", views.PublicScanView.as_view()),
    path("public/track/otp/", views.PublicTrackOtpView.as_view()),
    path("public/track/otp/verify/", views.PublicTrackOtpVerifyView.as_view()),
    path("public/track/additional/", views.PublicFollowUpView.as_view()),
    path("public/track/documents/<str:kind>/<uuid:file_id>/", views.PublicTrackDocumentView.as_view()),
    path("public/track/reply/", views.PublicReplyView.as_view()),
    path("admin/uploads/<uuid:pk>/", views.AdminUnsafeDocumentDeleteView.as_view()),
    path("admin/uploads/<uuid:pk>/scan/", views.AdminDocumentScanView.as_view()),
    path("admin/uploads/", views.AdminUploadsView.as_view()),
    path("reports/", reports.ReportListView.as_view()),
    path("reports/<str:key>/", reports.ReportView.as_view()),
    path("", include(router.urls)),
]

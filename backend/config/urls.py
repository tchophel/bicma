from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/", include("accounts.urls")),
    path("api/", include("core.urls")),
    path("api/", include("complaints.urls")),
]
if settings.DEBUG:
    urlpatterns.append(path("django-admin/", admin.site.urls))

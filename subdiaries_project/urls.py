from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
#from journal import views_diag as diag
from journal import views_diag

def health(request):
    import os
    return JsonResponse({"ok": True, "env": os.environ.get("DJANGO_SETTINGS_MODULE")})

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("journal.urls")),
    path("diag/secure/", diag.secure_probe, name="secure-probe"),
    path("", include(("journal.urls","journal"), namespace="journal")),
    path("health/", health, name="health"),
    path("accounts/", include("django.contrib.auth.urls")),  # <-- adds 'login', 'logout', etc.

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


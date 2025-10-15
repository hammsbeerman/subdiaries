from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
import os

# Always-available lightweight health check
def healthz(_request):
    return HttpResponse("ok\n", content_type="text/plain")

# --- Diagnostics (enabled only in DEBUG or via ENABLE_DIAG_ROUTES=1) ---
@csrf_exempt
def secure_probe(request):
    m = request.META
    return JsonResponse({
        "is_secure": request.is_secure(),
        "scheme": request.scheme,
        "headers": {
            "Host": m.get("HTTP_HOST"),
            "X-Forwarded-Proto": m.get("HTTP_X_FORWARDED_PROTO"),
            "X-Forwarded-Host": m.get("HTTP_X_FORWARDED_HOST"),
            "X-Forwarded-Port": m.get("HTTP_X_FORWARDED_PORT"),
            "Forwarded": m.get("HTTP_FORWARDED"),
        },
        "cookies": {
            "csrftoken_present": "csrftoken" in request.COOKIES,
            "session_present": settings.SESSION_COOKIE_NAME in request.COOKIES,
        },
        "settings": {
            "SESSION_COOKIE_SECURE": settings.SESSION_COOKIE_SECURE,
            "CSRF_COOKIE_SECURE": settings.CSRF_COOKIE_SECURE,
            "CSRF_TRUSTED_ORIGINS": settings.CSRF_TRUSTED_ORIGINS,
            "SECURE_PROXY_SSL_HEADER": settings.SECURE_PROXY_SSL_HEADER,
            "USE_X_FORWARDED_HOST": getattr(settings, "USE_X_FORWARDED_HOST", False),
            "SESSION_COOKIE_SAMESITE": getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax"),
            "CSRF_COOKIE_SAMESITE": getattr(settings, "CSRF_COOKIE_SAMESITE", "Lax"),
        },
    }, json_dumps_params={"indent": 2})

@ensure_csrf_cookie
def csrf_ping(_request):
    return HttpResponse("ok", content_type="text/plain")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("journal.urls")),
    path("healthz", healthz, name="healthz"),
]

# Toggle diag routes without rebuilding: export ENABLE_DIAG_ROUTES=1
if settings.DEBUG or os.getenv("ENABLE_DIAG_ROUTES", "").lower() in {"1", "true", "yes", "on"}:
    urlpatterns += [
        path("diag/secure/", secure_probe, name="secure-probe"),
        path("diag/csrf/", csrf_ping, name="csrf-ping"),
    ]
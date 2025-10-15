from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
import os
import io, traceback

# --- Core tiny endpoints ------------------------------------------------------
def healthz(_request):
    return HttpResponse("ok\n", content_type="text/plain")

def root_safe(request):
    try:
        if not request.user.is_authenticated:
            return HttpResponseRedirect("/accounts/login/?next=/")
        return HttpResponse("OK — logged in", content_type="text/plain")
    except Exception:
        buf = io.StringIO()
        traceback.print_exc(file=buf)
        return HttpResponse("ERROR\n" + buf.getvalue(), content_type="text/plain", status=500)

# --- Diagnostics (opt-in via DEBUG or ENABLE_DIAG_ROUTES) ---------------------
@csrf_exempt
def secure_probe(request):
    m = request.META
    return JsonResponse(
        {
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
        },
        json_dumps_params={"indent": 2},
    )

@ensure_csrf_cookie
def csrf_ping(_request):
    return HttpResponse("ok", content_type="text/plain")

# --- URL patterns -------------------------------------------------------------
urlpatterns = [
    path("", root_safe, name="root-safe"),                  # temporary safe “/”
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("journal.urls")),                      # everything else
    path("healthz", healthz, name="healthz"),
]

if settings.DEBUG or os.getenv("ENABLE_DIAG_ROUTES", "").lower() in {"1", "true", "yes", "on"}:
    urlpatterns += [
        path("diag/secure/", secure_probe, name="secure-probe"),
        path("diag/csrf/", csrf_ping, name="csrf-ping"),
    ]
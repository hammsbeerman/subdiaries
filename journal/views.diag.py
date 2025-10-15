from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

@csrf_exempt
def secure_probe(request):
    meta = request.META
    data = {
        "request": {
            "is_secure": request.is_secure(),
            "scheme": request.scheme,
            "method": request.method,
            "build_absolute_uri": request.build_absolute_uri("/"),
        },
        "headers": {
            "Host": meta.get("HTTP_HOST"),
            "X-Forwarded-Proto": meta.get("HTTP_X_FORWARDED_PROTO"),
            "X-Forwarded-Host": meta.get("HTTP_X_FORWARDED_HOST"),
            "X-Forwarded-Port": meta.get("HTTP_X_FORWARDED_PORT"),
            "Forwarded": meta.get("HTTP_FORWARDED"),
            "Referer": meta.get("HTTP_REFERER"),
            "User-Agent": meta.get("HTTP_USER_AGENT"),
            "Remote-Addr": meta.get("REMOTE_ADDR"),
            "Server-Port": meta.get("SERVER_PORT"),
        },
        "cookies_seen": {
            "csrftoken_present": "csrftoken" in request.COOKIES,
            "session_present": settings.SESSION_COOKIE_NAME in request.COOKIES,
        },
        "settings": {
            "DEBUG": settings.DEBUG,
            "ALLOWED_HOSTS": settings.ALLOWED_HOSTS,
            "CSRF_TRUSTED_ORIGINS": settings.CSRF_TRUSTED_ORIGINS,
            "SESSION_COOKIE_SECURE": settings.SESSION_COOKIE_SECURE,
            "CSRF_COOKIE_SECURE": settings.CSRF_COOKIE_SECURE,
            "SECURE_PROXY_SSL_HEADER": settings.SECURE_PROXY_SSL_HEADER,
            "USE_X_FORWARDED_HOST": getattr(settings, "USE_X_FORWARDED_HOST", False),
        },
    }
    return JsonResponse(data, json_dumps_params={"indent": 2})
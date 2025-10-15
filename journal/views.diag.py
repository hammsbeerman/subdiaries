from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

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
        },
        "cookies": {
            "csrftoken": "csrftoken" in request.COOKIES,
            "session": settings.SESSION_COOKIE_NAME in request.COOKIES,
        },
        "settings": {
            "SESSION_COOKIE_SECURE": settings.SESSION_COOKIE_SECURE,
            "CSRF_COOKIE_SECURE": settings.CSRF_COOKIE_SECURE,
            "CSRF_TRUSTED_ORIGINS": settings.CSRF_TRUSTED_ORIGINS,
            "SECURE_PROXY_SSL_HEADER": settings.SECURE_PROXY_SSL_HEADER,
            "USE_X_FORWARDED_HOST": getattr(settings, "USE_X_FORWARDED_HOST", False),
        }
    }, json_dumps_params={"indent": 2})
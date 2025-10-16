import os
from django.core.mail import send_mail
from django.conf import settings
from .models import Membership

def send_invite_email(to_email, subject, body):
    send_mail(subject, body, getattr(settings,"DEFAULT_FROM_EMAIL","no-reply@example.com"),
              [to_email], fail_silently=True)

def send_invite_sms(to_phone, body):
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    tok = os.getenv("TWILIO_AUTH_TOKEN")
    from_num = os.getenv("TWILIO_FROM_NUMBER")  # e.g. +15551234567
    if sid and tok and from_num:
        try:
            from twilio.rest import Client
            Client(sid, tok).messages.create(to=to_phone, from_=from_num, body=body)
            return
        except Exception:
            pass
    # Dev fallback
    print(f"[SMS to {to_phone}] {body}")

def get_user_org(user):
    """Return the first org for this user (or None)."""
    if not user or not user.is_authenticated:
        return None
    m = (Membership.objects
            .select_related("org")
            .filter(user=user)
            .order_by("id")
            .first())
    return m.org if m else None

def is_htmx(request):
    return request.headers.get("HX-Request") == "true"

def user_is_moderator(user):
    m = Membership.objects.filter(user=user).first()
    return bool(m and str(m.role).lower() in {"moderator","admin","owner"})

def can_manage_member(actor, membership):
    if not actor.is_authenticated:
        return False
    # org-level managers
    if user_is_moderator(actor):
        return True
    # parent can manage their own subusers
    return membership.managed_by_id == actor.id
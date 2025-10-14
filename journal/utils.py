import os
from django.core.mail import send_mail
from django.conf import settings

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
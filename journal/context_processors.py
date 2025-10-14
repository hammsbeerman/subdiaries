from .models import Membership

def org_and_role(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"org": None, "is_moderator": False}
    m = Membership.objects.filter(user=request.user).select_related("org").first()
    role = (m.role or "").lower() if m else ""
    return {"org": (m.org if m else None), "is_moderator": role in {"moderator","admin","owner"}}
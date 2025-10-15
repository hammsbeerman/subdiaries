from .models import Organization, Membership

def org_and_role(request):
    ctx = {"current_org": None, "is_moderator": False}
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return ctx

    org = Organization.objects.filter(membership__user=user).first()
    role = None
    if org:
        role = (Membership.objects
                .filter(user=user, org=org)
                .values_list("role", flat=True)
                .first())

    ctx["current_org"] = org
    ctx["is_moderator"] = role in {"OWNER", "ADMIN", "MODERATOR"}
    return ctx
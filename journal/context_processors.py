from .models import Organization, Membership

def org_and_role(request):
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return {
            "current_org": None,
            "is_moderator": False,
            "has_subusers": False,
            "show_review_queue": False,
        }

    # Get this user's membership (and org) with 1 query
    mem = (
        Membership.objects
        .select_related("org")
        .filter(user=user)
        .order_by("org__id")
        .first()
    )

    org = mem.org if mem else None
    role = mem.role if mem else None
    is_mod = role in {"OWNER", "ADMIN", "MODERATOR"}

    # Only compute has_subusers if the field exists and we have an org
    has_subusers = False
    if org and hasattr(Membership, "managed_by"):
        has_subusers = Membership.objects.filter(org=org, managed_by=user).exists()

    return {
        "current_org": org,
        "is_moderator": is_mod,
        "has_subusers": has_subusers,
        # Tweak this rule as you like:
        "show_review_queue": has_subusers or is_mod,
    }
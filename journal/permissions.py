from django.http import Http404
from django.contrib.auth import get_user_model
from .models import Membership, Organization

ROLE_ORDER = {"SUBAUTHOR": 0, "AUTHOR": 1, "MODERATOR": 2, "ADMIN": 3, "OWNER": 4}

def get_manager(user, org):
    """Return manager (master) user for this user in org, if any."""
    try:
        mem = Membership.objects.select_related("org").get(user=user, org=org)
        # assumes your Membership has managed_by (from earlier work)
        return getattr(mem, "managed_by", None)
    except Membership.DoesNotExist:
        return None

def can_view_profile(viewer, subject):
    if not (viewer and viewer.is_authenticated):
        return False
    if viewer == subject:
        return True
    # same org + viewer is subject's manager
    try:
        # subject.mem.managed_by == viewer
        return Membership.objects.filter(user=subject, managed_by=viewer).exists()
    except Exception:
        return False

def can_edit_profile(viewer, subject):
    # only self or manager can edit
    return can_view_profile(viewer, subject)

def user_org(user):
    return (Organization.objects
            .filter(memberships__user=user)
            .order_by("id")
            .first())

def user_role_in_org(user, org):
    return (Membership.objects
            .filter(user=user, org=org)
            .values_list("role", flat=True)
            .first())

def can_manage(manager, target):
    """Manager can edit themself or anyone in same org with lower role."""
    if manager.id == target.id:
        return True
    org = user_org(manager)
    if not org:
        return False
    # must share org
    if not Membership.objects.filter(user=target, org=org).exists():
        return False
    m_role = user_role_in_org(manager, org) or "SUBAUTHOR"
    t_role = user_role_in_org(target,  org) or "SUBAUTHOR"
    return ROLE_ORDER.get(m_role, -1) > ROLE_ORDER.get(t_role, -1)

def get_target_user_or_404(request_user, user_id: int | None):
    U = get_user_model()
    if user_id is None:
        return request_user
    try:
        target = U.objects.get(pk=user_id)
    except U.DoesNotExist:
        raise Http404("User not found")
    if not can_manage(request_user, target):
        raise Http404()  # hide existence
    return target
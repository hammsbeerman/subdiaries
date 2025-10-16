from django import template
from journal.models import Membership, Organization

register = template.Library()

def _role_rank(role: str) -> int:
    order = {"OWNER": 4, "ADMIN": 3, "MODERATOR": 2, "AUTHOR": 1, "SUBAUTHOR": 0}
    return order.get(role or "", -1)

def user_can_manage_user(actor, target) -> bool:
    if not getattr(actor, "is_authenticated", False):
        return False
    if actor.is_superuser:
        return True
    # same org?
    org = (Organization.objects
           .filter(memberships__user=actor)
           .order_by("id")
           .first())
    if not org:
        return False
    a_role = (Membership.objects
              .filter(user=actor, org=org)
              .values_list("role", flat=True)
              .first())
    t_role = (Membership.objects
              .filter(user=target, org=org)
              .values_list("role", flat=True)
              .first())
    if not a_role or not t_role:
        return False
    return _role_rank(a_role) > _role_rank(t_role)

@register.filter(name="can_manage")
def can_manage(actor, target_user):
    return user_can_manage_user(actor, target_user)
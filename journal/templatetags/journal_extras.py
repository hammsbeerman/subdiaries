from django import template
from journal.utils import user_is_moderator, can_manage_member  # you added can_manage_member earlier

register = template.Library()

@register.filter
def can_manage(user, membership):
    """
    Usage: {% if request.user|can_manage:m %} … {% endif %}
    """
    try:
        return user_is_moderator(user) or can_manage_member(user, membership)
    except Exception:
        return False
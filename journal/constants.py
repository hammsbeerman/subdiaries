"""
Central place for role-related constants.
Prefers the model’s live choices; falls back to static tuple if models
aren’t importable at import time (e.g., during early commands).
"""

from typing import List, Tuple

# Fallback (kept in sync with models.Membership.Role)
_FALLBACK_ROLE_CHOICES: Tuple[Tuple[str, str], ...] = (
    ("OWNER", "Owner"),
    ("ADMIN", "Admin"),
    ("MODERATOR", "Moderator"),
    ("AUTHOR", "Author"),
    ("SUBAUTHOR", "Sub-author"),
)

def get_role_choices() -> List[Tuple[str, str]]:
    """Return role choices, using the Membership model if available."""
    try:
        # Lazy import to avoid circulars
        from .models import Membership
        return list(Membership.Role.choices)
    except Exception:
        return list(_FALLBACK_ROLE_CHOICES)

# Materialize a module-level constant for templates/views that just need a tuple
ROLE_CHOICES: Tuple[Tuple[str, str], ...] = tuple(get_role_choices())

# Convenience: map code -> label, e.g., ROLE_LABELS["MODERATOR"] == "Moderator"
ROLE_LABELS = {code: label for code, label in ROLE_CHOICES}
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Organization, Membership, UserProfile, RoleAlias,
    Tab, Entry, EntryImage
)

User = get_user_model()

# --- Simple models ---
@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner")
    search_fields = ("name", "owner__username", "owner__email")
    list_select_related = ("owner",)

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "org", "role")
    list_filter = ("org", "role")
    search_fields = ("user__username", "user__email", "org__name")
    list_select_related = ("user", "org")
    raw_id_fields = ("user", "org")

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "display_name")
    search_fields = ("user__username", "user__email", "display_name")
    list_select_related = ("user",)

# Be conservative here since field names vary; default admin won’t break.
@admin.register(RoleAlias)
class RoleAliasAdmin(admin.ModelAdmin):
    pass

@admin.register(Tab)
class TabAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "org", "enabled")
    list_filter = ("enabled", "org")
    search_fields = ("name", "org__name")
    list_select_related = ("org",)

# --- Entries with inline images ---
class EntryImageInline(admin.TabularInline):
    model = EntryImage
    extra = 0

@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "org", "author", "created_at")
    list_filter = ("org", "author")
    search_fields = ("title", "author__username", "org__name")
    list_select_related = ("org", "author")
    inlines = [EntryImageInline]

@admin.register(EntryImage)
class EntryImageAdmin(admin.ModelAdmin):
    list_display = ("id", "entry", "image", "uploaded_at")
    list_select_related = ("entry",)
    raw_id_fields = ("entry",)

# --- User admin (keep Django’s features + add inlines) ---
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    fk_name = "user"          # <-- important: pick the correct FK to auth.User
    can_delete = False
    extra = 0

class MembershipInline(admin.TabularInline):
    model = Membership
    fk_name = "user"
    extra = 0
    raw_id_fields = ("org",)

# Remove the built-in registration safely, then re-register with inlines.
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = [UserProfileInline, MembershipInline]
    list_display = ("username", "email", "first_name", "last_name", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")
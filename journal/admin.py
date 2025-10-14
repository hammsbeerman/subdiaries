
from django.contrib import admin
from .models import Organization, Membership, UserProfile, RoleAlias, Tab, Entry, EntryImage

admin.site.register(Organization)
admin.site.register(Membership)
admin.site.register(UserProfile)
admin.site.register(RoleAlias)
admin.site.register(Tab)


class EntryImageInline(admin.TabularInline):
    model = EntryImage
    extra = 0

@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_at")
    inlines = [EntryImageInline]

@admin.register(EntryImage)
class EntryImageAdmin(admin.ModelAdmin):
    list_display = ("id", "entry", "image", "uploaded_at")

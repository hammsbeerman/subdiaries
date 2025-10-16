from django.db import models
from django.conf import settings  # <-- needed for AUTH_USER_MODEL
from django.utils.text import slugify
from django.core.validators import FileExtensionValidator
from django.utils import timezone
import secrets
from django.db.models import JSONField  # works on MySQL 8+


def profile_upload_path(instance, filename):
    return f"profiles/{instance.user_id}/{filename}"

def _unique_tab_slug(org, name):
    base = slugify(name) or "tab"
    slug = base
    i = 2
    from .models import Tab  # local import if this helper sits above Tab
    while Tab.objects.filter(org=org, slug=slug).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug

# --- Core ---

class Organization(models.Model):
    name = models.CharField(max_length=128, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name="owned_orgs", db_index=True)
    requires_two_stage = models.BooleanField(default=True)
    def __str__(self): return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        ADMIN = "ADMIN", "Admin"
        MODERATOR = "MODERATOR", "Moderator"
        AUTHOR = "AUTHOR", "Author"
        SUBAUTHOR = "SUBAUTHOR", "Subauthor"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="memberships", db_index=True)
    org  = models.ForeignKey(Organization, on_delete=models.CASCADE,
                             related_name="memberships", db_index=True)
    role = models.CharField(max_length=16, choices=Role.choices, db_index=True)
    managed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="managed_memberships"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "org"], name="uniq_membership_user_org"),
        ]
        indexes = [models.Index(fields=["org", "role"])]

    def __str__(self): return f"{self.user.username}@{self.org.name}({self.role})"


class UserProfile(models.Model):
    # Prefer AUTH_USER_MODEL everywhere for consistency
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=120, blank=True)
    parent = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="subusers")
    full_name = models.CharField(max_length=120, blank=True)
    pet_name = models.CharField(max_length=120, blank=True)
    about = models.TextField(blank=True)
    onboarding_enabled = models.BooleanField(default=True)
    onboarding_step = models.PositiveSmallIntegerField(default=1)  # 1..5
    about_me    = models.TextField(blank=True)
    nicknames   = JSONField(default=list, blank=True)      # ["AJ","Coach"]
    profile_pic = models.ImageField(
        upload_to=profile_upload_path, blank=True, null=True,
        validators=[FileExtensionValidator(["jpg","jpeg","png","webp"])],
    )
    # arbitrary custom fields (key/value/type)
    custom_fields = JSONField(default=list, blank=True)    # [{"key":"Hobby","value":"Fishing","type":"text"}]

    # visibility flags if you ever need (kept simple here)
    # allow_manager_view = models.BooleanField(default=True)

    def __str__(self):
        return self.display_name or self.user.get_username()


class ProfileImage(models.Model):
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="images")
    image   = models.ImageField(
        upload_to=profile_upload_path,
        validators=[FileExtensionValidator(["jpg","jpeg","png","webp"])],
    )
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-is_primary", "-id"]

    def __str__(self):
        return self.caption or self.image.name
    


class RoleAlias(models.Model):
    org = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="role_alias")
    moderator_label = models.CharField(max_length=40, default="Moderator")
    author_label = models.CharField(max_length=40, default="Author")
    subuser_label = models.CharField(max_length=40, default="Subuser")


# --- Content ---

class Tab(models.Model):
    org = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="tabs", db_index=True)
    name = models.CharField(max_length=64)
    slug = models.SlugField(max_length=120)
    enabled = models.BooleanField(default=True, db_index=True)
    visibility = models.IntegerField(default=20)  # 10=subuser,20=author,30=moderator,40=admin
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="created_tabs")

    def save(self, *args, **kwargs):
        if not self.slug and self.org_id:
            base = slugify(self.name) or "tab"
            slug = base
            i = 2
            while Tab.objects.filter(org=self.org, slug=slug).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["org", "slug"], name="uniq_tab_slug_per_org"),
            models.UniqueConstraint(fields=["org", "name"], name="uniq_tab_name_per_org"),
        ]
        indexes = [models.Index(fields=["org", "enabled", "name"])]

    def __str__(self): return f"{self.name} ({self.org.name})"


class Entry(models.Model):
    class Status(models.IntegerChoices):
        DRAFT = 0, "Draft"
        PENDING = 1, "Pending"
        APPROVED = 2, "Approved"
        REJECTED = 3, "Rejected"

    org = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="entries", db_index=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="entries", db_index=True)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                 related_name="reviewed_entries", null=True, blank=True)

    title = models.CharField(max_length=200)
    body  = models.TextField(blank=True)
    tabs  = models.ManyToManyField("Tab", related_name="entries", blank=True)

    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at   = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    approved_at  = models.DateTimeField(null=True, blank=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)

    status = models.PositiveSmallIntegerField(choices=Status.choices,
                                              default=Status.DRAFT, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["org", "status", "-created_at"]),     # review/index pages
            models.Index(fields=["author", "status", "-created_at"]),  # drafts page
        ]


def entry_image_path(instance, filename):
    return f"entry_images/{instance.entry_id}/{filename}"


class EntryImage(models.Model):
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name="images", db_index=True)
    image = models.ImageField(upload_to=entry_image_path)
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.entry_id} – {self.image.name}"

class Invite(models.Model):
    DELIVERY_CHOICES = [("email","Email"), ("sms","SMS")]

    org   = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invites")
    role  = models.CharField(max_length=16, choices=Membership.Role.choices)
    delivery = models.CharField(max_length=10, choices=DELIVERY_CHOICES, default="email")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)  # store E.164 like +15551234567

    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_invites")
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="accepted_invites")

    def mark_used(self, user=None):
        self.used_at = timezone.now()
        if user and not self.accepted_by_id:
            self.accepted_by = user
        self.save(update_fields=["used_at","accepted_by"])

    @classmethod
    def create(cls, *, org, role, created_by, email="", phone="", ttl_hours=72, delivery="email"):
        return cls.objects.create(
            org=org, role=role, created_by=created_by,
            email=email.strip().lower(), phone=phone.strip(),
            delivery=delivery,
            token=secrets.token_urlsafe(32),
            expires_at=timezone.now() + timezone.timedelta(hours=ttl_hours),
        )

    def is_valid(self):
        return self.used_at is None and timezone.now() < self.expires_at

class SocialLink(models.Model):
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="socials")
    platform = models.CharField(max_length=50)         # e.g. "Twitter"
    handle = models.CharField(max_length=120, blank=True)
    url = models.URLField(max_length=500)
    visible = models.BooleanField(default=True)

    class Meta:
        ordering = ["platform", "handle"]

    def __str__(self):
        return f"{self.platform}: {self.handle or self.url}"

FIELD_KIND_CHOICES = [("text","Text"),("url","URL"),("date","Date"),("number","Number")]

class CustomField(models.Model):
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="custom_items", related_query_name="custom_item",)
    label = models.CharField(max_length=120)
    value = models.TextField(blank=True)
    kind = models.CharField(max_length=20, choices=FIELD_KIND_CHOICES, default="text")
    visible = models.BooleanField(default=True)

    class Meta:
        ordering = ["label"]

    def __str__(self):
        return f"{self.label}: {self.value}"

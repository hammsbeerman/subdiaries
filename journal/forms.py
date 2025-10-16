
from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth import get_user_model

from .models import (
    Entry, Tab, Membership, Invite,
    UserProfile, SocialLink, ProfileImage, CustomField
)

User = get_user_model()

# -----------------------
# Shared / helpers
# -----------------------
class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

ROLE_CHOICES = [
    ("MODERATOR", "Moderator"),
    ("AUTHOR", "Author"),
    ("SUBAUTHOR", "Subauthor"),
]

# -----------------------
# Entries / Tabs
# -----------------------
class EntryForm(forms.ModelForm):
    images = forms.FileField(required=False, widget=MultiFileInput(attrs={"multiple": True}))
    tabs = forms.ModelMultipleChoiceField(queryset=Tab.objects.all(), required=False)

    class Meta:
        model = Entry
        fields = ["title", "body", "tabs"]  # add any additional Entry fields you use

class TabForm(forms.ModelForm):
    class Meta:
        model = Tab
        fields = ["name", "enabled"]
        widgets = {"name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Family Updates"})}

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split()).strip()

class TabRenameForm(forms.ModelForm):
    class Meta:
        model = Tab
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Tab name"})}

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split()).strip()

# -----------------------
# Membership / Invites
# -----------------------
class MemberAddForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    password = forms.CharField(
        required=False, widget=forms.PasswordInput, help_text="Leave blank to auto-generate."
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

class InviteForm(forms.Form):
    delivery = forms.ChoiceField(choices=[("email", "Email"), ("sms", "SMS")], initial="email")
    email = forms.EmailField(required=False)
    phone = forms.CharField(required=False, help_text="E.164 like +15551234567")
    role = forms.ChoiceField(choices=ROLE_CHOICES)

    def clean(self):
        data = super().clean()
        d = data.get("delivery")
        if d == "email" and not data.get("email"):
            self.add_error("email", "Email required.")
        if d == "sms" and not data.get("phone"):
            self.add_error("phone", "Phone required.")
        return data

class AcceptInviteForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        if data.get("password") != data.get("confirm_password"):
            raise forms.ValidationError("Passwords do not match.")
        if User.objects.filter(username__iexact=data.get("username", "")).exists():
            self.add_error("username", "Username already exists.")
        return data

class SubuserCreateForm(forms.Form):
    full_name = forms.CharField(max_length=150, required=False, label="Name")
    email = forms.EmailField(required=False)
    phone = forms.CharField(required=False, label="SMS (optional)")
    role = forms.ChoiceField(choices=[(Membership.Role.SUBAUTHOR, "Sub-author")], initial=Membership.Role.SUBAUTHOR)

    def clean(self):
        data = super().clean()
        if not data.get("email") and not data.get("phone"):
            raise forms.ValidationError("Provide at least an email or a phone.")
        return data

# -----------------------
# Profile (top form)
# -----------------------
class ProfileMiniForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        # If your model uses full_name/about_me, rename here accordingly.
        fields = ["display_name"]
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Your display name"})
        }

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["full_name", "about_me", "profile_pic", "nicknames"]
        widgets = {
            "about_me": forms.Textarea(attrs={"rows": 4}),
            "nicknames": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": "Comma or newline separated (e.g. Addy, A.K.)",
                }
            ),
        }
        help_texts = {
            "nicknames": "Separate multiple nicknames with commas or new lines.",
        }

    # Optional: normalize on save
    def save(self, commit=True):
        obj = super().save(commit=False)
        # Ensure consistent comma-separated storage
        text = (obj.nicknames or "").replace("\r\n", "\n")
        parts = [s.strip() for s in re.split(r"[,\n]+", text) if s.strip()]
        obj.nicknames = ", ".join(dict.fromkeys(parts))  # de-dup, keep order
        if commit:
            obj.save()
        return obj

# -----------------------
# Socials
# -----------------------
class SocialLinkForm(forms.ModelForm):
    class Meta:
        model = SocialLink
        fields = ["platform", "handle", "url", "visible"]
        widgets = {
            "platform": forms.TextInput(attrs={"class": "form-control", "placeholder": "Twitter / Instagram / …"}),
            "handle":   forms.TextInput(attrs={"class": "form-control", "placeholder": "@name or user id"}),
            "url":      forms.URLInput(attrs={"class": "form-control", "placeholder": "https://…"}),
            "visible":  forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

SocialFormSet = inlineformset_factory(
    parent_model=UserProfile,
    model=SocialLink,
    form=SocialLinkForm,
    extra=0,
    can_delete=True,
    min_num=0, validate_min=False, max_num=1000, validate_max=False,
)

# -----------------------
# Images
# -----------------------
class ProfileImageForm(forms.ModelForm):
    class Meta:
        model = ProfileImage
        fields = ["image", "caption", "is_primary", "visible"]
        widgets = {
            "caption":    forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional caption"}),
            "is_primary": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "visible":    forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

ImageFormSet = inlineformset_factory(
    parent_model=UserProfile,
    model=ProfileImage,
    form=ProfileImageForm,
    extra=0,
    can_delete=True,
    min_num=0, validate_min=False, max_num=1000, validate_max=False,
)

# -----------------------
# Custom fields
# -----------------------
class CustomFieldItemForm(forms.ModelForm):
    class Meta:
        model = CustomField
        # IMPORTANT: if your model was using `key` instead of `label`, change here.
        fields = ["label", "value", "kind", "visible"]
        widgets = {
            "label":   forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Favorite Color"}),
            "value":   forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Purple"}),
            "kind":    forms.Select(attrs={"class": "form-select"}),
            "visible": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

CustomFieldFormSet = inlineformset_factory(
    parent_model=UserProfile,
    model=CustomField,
    form=CustomFieldItemForm,
    extra=0,
    can_delete=True,
    min_num=0, validate_min=False, max_num=1000, validate_max=False,
)
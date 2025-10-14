
from django import forms
from django.contrib.auth import get_user_model
from .models import Entry, Tab, Membership, Invite, UserProfile



class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class EntryForm(forms.ModelForm):
    images = forms.FileField(
        required=False,
        widget=MultiFileInput(attrs={"multiple": True})
    )
    tabs = forms.ModelMultipleChoiceField(
        queryset=Tab.objects.all(),  # or filtered per user
        required=False
    )

    class Meta:
        model = Entry
        fields = ["title", "body", "tabs"]  # plus any other Entry fields you use

ROLE_CHOICES = [
    ("MODERATOR","Moderator"),
    ("AUTHOR","Author"),
    ("SUBAUTHOR","Subauthor"),
]

class MemberAddForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    password = forms.CharField(
        required=False, widget=forms.PasswordInput, help_text="Leave blank to auto-generate."
    )

    def clean_username(self):
        U = get_user_model()
        username = self.cleaned_data["username"].strip()
        if U.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

ROLE_CHOICES = [("MODERATOR","Moderator"), ("AUTHOR","Author"), ("SUBAUTHOR","Subauthor")]

class InviteForm(forms.Form):
    delivery = forms.ChoiceField(choices=[("email","Email"),("sms","SMS")], initial="email")
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
        U = get_user_model()
        if U.objects.filter(username__iexact=data.get("username","")).exists():
            self.add_error("username", "Username already exists.")
        return data

class TabForm(forms.ModelForm):
    class Meta:
        model = Tab
        fields = ["name", "enabled"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Family Updates"}),
            # no disabled attrs here so it’s clickable
        }

    def clean_name(self):
        # normalize spaces
        return " ".join(self.cleaned_data["name"].split()).strip()

class TabRenameForm(forms.ModelForm):
    class Meta:
        model = Tab
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Tab name"}),
        }

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split()).strip()

class ProfileMiniForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["full_name"]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Your display name"})
        }
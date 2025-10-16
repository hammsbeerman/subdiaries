from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from journal.models import UserProfile
from .utils import make_user, make_org, add_member

User = get_user_model()

class ProfileEditViewTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner", first_name="Own")
        self.target = make_user("target", first_name="Tar")
        self.org = make_org(self.owner)
        add_member(self.target, self.org, "AUTHOR")

    def login(self, user):
        self.client.login(username=user.username, password="pass")

    def test_self_profile_edit_get(self):
        self.login(self.owner)
        url = reverse("journal:profile_edit")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("form", r.context)
        self.assertIn("social_fs", r.context)
        self.assertTemplateUsed(r, "journal/profile_edit.html")

    def test_manage_subuser_allowed(self):
        # owner can edit AUTHOR
        self.login(self.owner)
        url = reverse("journal:profile_edit_user", args=[self.target.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_manage_subuser_forbidden_for_lower_role(self):
        # target cannot edit owner
        self.login(self.target)
        url = reverse("journal:profile_edit_user", args=[self.owner.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

    def test_post_save_profile(self):
        self.login(self.owner)
        profile, _ = UserProfile.objects.get_or_create(user=self.owner)

        url = reverse("journal:profile_edit")
        # Minimal POST with formset management forms
        data = {
            "display_name": "Owner Name",
            "nickname": "",
            # social formset
            "social-TOTAL_FORMS": "0",
            "social-INITIAL_FORMS": "0",
            "social-MIN_NUM_FORMS": "0",
            "social-MAX_NUM_FORMS": "1000",
            # image formset
            "image-TOTAL_FORMS": "0",
            "image-INITIAL_FORMS": "0",
            "image-MIN_NUM_FORMS": "0",
            "image-MAX_NUM_FORMS": "1000",
            # custom formset
            "custom-TOTAL_FORMS": "0",
            "custom-INITIAL_FORMS": "0",
            "custom-MIN_NUM_FORMS": "0",
            "custom-MAX_NUM_FORMS": "1000",
        }
        r = self.client.post(url, data)
        self.assertIn(r.status_code, (302,))  # redirect after save
        profile.refresh_from_db()
        self.assertEqual(profile.display_name, "Owner Name")
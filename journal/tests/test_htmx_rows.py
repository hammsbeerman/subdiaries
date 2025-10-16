from django.test import TestCase
from django.urls import reverse
from .utils import make_user, make_org, add_member

class HTMXRowEndpointsTests(TestCase):
    def setUp(self):
        self.owner = make_user("boss")
        self.target = make_user("staff")
        self.org = make_org(self.owner)
        add_member(self.target, self.org, "AUTHOR")
        self.client.login(username="boss", password="pass")

    def test_add_social_row(self):
        r = self.client.get(reverse("journal:profile_social_row") + "?index=1",
                            HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        self.assertIn("profile_social_row.html", [t.name for t in r.templates])

    def test_add_image_row_for_user(self):
        r = self.client.get(reverse("journal:profile_image_row_user", args=[self.target.id]) + "?index=2",
                            HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)

    def test_add_custom_row_forbidden_if_no_perm(self):
        # log in as target; they can’t manage boss
        self.client.logout()
        self.client.login(username="staff", password="pass")
        r = self.client.get(reverse("journal:profile_custom_row_user", args=[self.owner.id]) + "?index=0",
                            HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 403)
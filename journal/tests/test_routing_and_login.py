from django.test import TestCase
from django.urls import reverse
from .utils import make_user, make_org, add_member

class RoutingAndLoginTests(TestCase):
    def setUp(self):
        self.u = make_user("alice")
        self.org = make_org(self.u)

    def test_root_requires_login_redirects(self):
        r = self.client.get("/", follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("/accounts/login"))

    def test_login_redirects_to_profile(self):
        # ensure LOGIN_REDIRECT_URL is /profile/ (as we changed)
        login_url = reverse("login")
        r = self.client.post(login_url, {"username": "alice", "password": "pass"}, follow=False)
        # should redirect somewhere (we expect /profile/ or your profile page)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/profile", r["Location"])
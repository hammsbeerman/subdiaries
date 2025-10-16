from django.test import TestCase
from django.contrib.auth import get_user_model
from journal.templatetags.can_manage import user_can_manage_user, _role_rank
from .utils import make_user, make_org, add_member

User = get_user_model()

class CanManageFilterTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner")
        self.admin = make_user("admin")
        self.mod   = make_user("mod")
        self.author= make_user("author")
        self.sub   = make_user("sub")
        self.outsider = make_user("outsider")
        self.org = make_org(self.owner)
        add_member(self.admin, self.org, "ADMIN")
        add_member(self.mod,   self.org, "MODERATOR")
        add_member(self.author,self.org, "AUTHOR")
        add_member(self.sub,   self.org, "SUBAUTHOR")

    def test_role_rank(self):
        self.assertGreater(_role_rank("ADMIN"), _role_rank("AUTHOR"))

    def test_can_manage_down_chain(self):
        self.assertTrue(user_can_manage_user(self.owner, self.admin))
        self.assertTrue(user_can_manage_user(self.admin, self.mod))
        self.assertTrue(user_can_manage_user(self.mod, self.author))
        self.assertTrue(user_can_manage_user(self.author, self.sub))

    def test_cannot_manage_same_or_higher(self):
        self.assertFalse(user_can_manage_user(self.admin, self.owner))
        self.assertFalse(user_can_manage_user(self.mod, self.admin))
        self.assertFalse(user_can_manage_user(self.author, self.mod))

    def test_cannot_manage_if_not_in_same_org(self):
        other = make_user("other")
        # no membership for other in org
        self.assertFalse(user_can_manage_user(self.mod, other))

    def test_superuser_can_manage_anyone(self):
        su = make_user("su", is_superuser=True, is_staff=True)
        self.assertTrue(user_can_manage_user(su, self.owner))
        self.assertTrue(user_can_manage_user(su, self.outsider))
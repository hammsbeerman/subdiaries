from django.contrib.auth import get_user_model
from journal.models import Organization, Membership

User = get_user_model()

def make_user(username="u", **kw):
    return User.objects.create_user(username=username, password="pass", **kw)

def make_org(owner=None, name="Org"):
    if owner is None:
        owner = make_user("owner")
    org = Organization.objects.create(name=name, owner=owner)
    Membership.objects.create(user=owner, org=org, role="OWNER")
    return org

def add_member(user, org, role="AUTHOR"):
    return Membership.objects.create(user=user, org=org, role=role)
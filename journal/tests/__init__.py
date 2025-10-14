import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from journal.models import Organization, Membership, Entry, Tab

@pytest.mark.django_db
def test_index_requires_login(client):
    r = client.get(reverse("journal:index"))
    assert r.status_code == 302 and "/accounts/login" in r["Location"]

@pytest.mark.django_db
def test_new_entry_flow(client):
    U = get_user_model()
    u = U.objects.create_user("adam","a@x.com","pw")
    org = Organization.objects.create(name="My Org", owner=u)
    Membership.objects.create(user=u, org=org, role="moderator")
    client.login(username="adam", password="pw")

    # GET form
    r = client.get(reverse("journal:entry_create"))
    assert r.status_code == 200

    # POST draft (no tabs, should auto default)
    r = client.post(reverse("journal:entry_create"), {
        "title":"T1","body":"B1","save":"1"
    }, follow=True)
    assert r.status_code == 200
    e = Entry.objects.get(title="T1")
    assert e.org == org and e.status == Entry.Status.DRAFT
    assert e.tabs.exists()  # default tab applied

@pytest.mark.django_db
def test_tabs_page(client):
    U = get_user_model()
    u = U.objects.create_user("adam2","b@x.com","pw")
    org = Organization.objects.create(name="Org2", owner=u)
    Membership.objects.create(user=u, org=org, role="moderator")
    Tab.objects.create(name="General", org=org, enabled=True)
    client.login(username="adam2", password="pw")
    r = client.get(reverse("journal:tabs"))
    assert r.status_code == 200
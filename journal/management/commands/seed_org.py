
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from journal.models import Organization, Membership

class Command(BaseCommand):
    help = "Create default Organization and attach superuser as OWNER."
    def handle(self, *args, **kwargs):
        owner = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not owner:
            self.stdout.write("Create a user first (createsuperuser).")
            return
        org, _ = Organization.objects.get_or_create(name="Default Org", owner=owner)
        Membership.objects.get_or_create(org=org, user=owner, role=Membership.Role.OWNER)
        self.stdout.write(self.style.SUCCESS(f"Seeded '{org.name}' with owner {owner.username}"))

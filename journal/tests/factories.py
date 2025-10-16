import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory, ImageField

from journal.models import (
    Organization,
    Membership,
    UserProfile,
    SocialLink,
    ProfileImage,
    CustomField,
)

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    is_staff = False
    is_superuser = False

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        # Usage: UserFactory(password="pass") or default "pass"
        pwd = extracted or "pass"
        self.set_password(pwd)
        if create:
            self.save()


class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Org {n}")
    owner = factory.SubFactory(UserFactory)

    @factory.post_generation
    def owner_membership(self, create, extracted, **kwargs):
        # Ensure the owner is a member with OWNER role
        if create:
            Membership.objects.get_or_create(
                user=self.owner, org=self, defaults={"role": "OWNER"}
            )


class MembershipFactory(DjangoModelFactory):
    class Meta:
        model = Membership

    user = factory.SubFactory(UserFactory)
    org = factory.SubFactory(OrganizationFactory)
    role = "AUTHOR"  # change as needed in tests


class UserProfileFactory(DjangoModelFactory):
    class Meta:
        model = UserProfile

    user = factory.SubFactory(UserFactory)
    display_name = factory.Faker("name")
    about = factory.Faker("sentence")
    # If your model has these fields, uncomment as needed:
    # profile_pic = ImageField(color="gray")
    # nicknames = factory.LazyFunction(list)  # or set a default list


class SocialLinkFactory(DjangoModelFactory):
    class Meta:
        model = SocialLink

    profile = factory.SubFactory(UserProfileFactory)
    platform = "Twitter"
    handle = factory.Sequence(lambda n: f"@handle{n}")
    url = factory.LazyAttribute(lambda o: f"https://twitter.com/{o.handle.strip('@')}")


class ProfileImageFactory(DjangoModelFactory):
    class Meta:
        model = ProfileImage

    profile = factory.SubFactory(UserProfileFactory)
    image = ImageField(color="gray")  # requires Pillow (factory_boy dep pulls it in)
    caption = factory.Faker("sentence")


class CustomFieldFactory(DjangoModelFactory):
    class Meta:
        model = CustomField

    profile = factory.SubFactory(UserProfileFactory)
    label = factory.Sequence(lambda n: f"Field {n}")
    value = factory.Faker("sentence")
    kind = "text"  # e.g., 'text' | 'url' | 'date' etc.

__all__ = [
    "UserFactory",
    "OrganizationFactory",
    "MembershipFactory",
    "UserProfileFactory",
    "SocialLinkFactory",
    "ProfileImageFactory",
    "CustomFieldFactory",
]
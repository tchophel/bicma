import os

from django.core.management.base import BaseCommand

from accounts.models import Division, Role, User
from core.models import Category, Dzongkhag, Subcategory, SystemConfiguration

DEFAULT_DIVISIONS = [
    ("Telecommunications", "TEL"),
    ("Broadcasting and Media", "MED"),
    ("Internet and Online Platforms", "NET"),
]
DZONGKHAGS = [
    "Bumthang", "Chhukha", "Dagana", "Gasa", "Haa", "Lhuentse", "Mongar", "Paro", "Pemagatshel",
    "Punakha", "Samdrup Jongkhar", "Samtse", "Sarpang", "Thimphu", "Trashigang", "Trashiyangtse",
    "Trongsa", "Tsirang", "Wangdue Phodrang", "Zhemgang",
]
DEFAULT_CATEGORIES = {
    "Telecommunications service": ["Network quality", "Billing", "Customer service"],
    "Internet service": ["Speed and reliability", "Billing", "Customer service"],
    "Cable television": ["Service interruption", "Billing", "Content"],
    "Broadcast and media content": ["Inaccurate reporting", "Harmful content", "Advertising"],
    "Social media and online content": ["Harassment", "Impersonation", "Harmful content", "Privacy"],
    "Other": [],
}


class Command(BaseCommand):
    help = "Idempotent first-run setup: default divisions, categories, settings and the initial Super Administrator."

    def handle(self, *args, **opts):
        if not Division.objects.exists():
            for name, code in DEFAULT_DIVISIONS:
                Division.objects.create(name=name, code=code)
            self.stdout.write("Created default divisions (editable in the UI).")
        if not SystemConfiguration.objects.filter(key="dzongkhags_seeded").exists():
            have = {n.lower() for n in Dzongkhag.objects.values_list("name", flat=True)}
            Dzongkhag.objects.bulk_create([Dzongkhag(name=n) for n in DZONGKHAGS if n.lower() not in have])
            SystemConfiguration.objects.create(key="dzongkhags_seeded", value="1", description="Initial Dzongkhag list loaded (one-time)")
            self.stdout.write("Loaded the 20 Dzongkhags. Gewogs are added in the admin UI (Master data > Gewogs).")
        if not Category.objects.exists():
            for cat, subs in DEFAULT_CATEGORIES.items():
                c = Category.objects.create(name=cat)
                Subcategory.objects.bulk_create([Subcategory(category=c, name=s) for s in subs])
            self.stdout.write("Created default categories (editable in the UI).")
        SystemConfiguration.objects.get_or_create(
            key="reference_prefix", defaults={"value": "BICMA-CMS", "description": "Prefix of complaint reference numbers"}
        )
        email = os.environ.get("BICMA_ADMIN_EMAIL")
        password = os.environ.get("BICMA_ADMIN_PASSWORD")
        if email and password and not User.objects.filter(role=Role.SUPER_ADMIN).exists():
            User.objects.create_user(email=email, password=password, role=Role.SUPER_ADMIN, is_staff=True)
            self.stdout.write(f"Created initial Super Administrator {email}.")

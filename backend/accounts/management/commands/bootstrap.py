import os

from django.core.management.base import BaseCommand

from accounts.models import Division, Role, User
from core.models import Category, Dzongkhag, Subcategory, SystemConfiguration

DEFAULT_DIVISIONS = [
    ("Spectrum and Technology Division", "SPT"),
    ("InfoComm and Infrastructure Division", "ICI"),
    ("Media and Content Division", "MCD"),
]
DZONGKHAGS = [
    "Bumthang", "Chhukha", "Dagana", "Gasa", "Haa", "Lhuentse", "Mongar", "Paro", "Pemagatshel",
    "Punakha", "Samdrup Jongkhar", "Samtse", "Sarpang", "Thimphu", "Trashigang", "Trashiyangtse",
    "Trongsa", "Tsirang", "Wangdue Phodrang", "Zhemgang",
]
# category -> (default division code, [subcategories], urban division code, rural division code)
DEFAULT_CATEGORIES = {
    "Radio-frequency interference": ("SPT", ["Interference"], None, None),
    "Spectrum / apparatus licensing and type approval": ("SPT", ["Type approval", "Apparatus licence"], None, None),
    "Quality of service": ("SPT", ["Voice quality", "Data speed"], None, None),
    "Network coverage": ("SPT", ["Coverage"], "SPT", "ICI"),
    "Billing dispute": ("ICI", ["Overcharging", "Unrecognised charges"], None, None),
    "Service interruption": ("ICI", ["Outage", "Slow service"], None, None),
    "Tariffs": ("ICI", [], None, None),
    "Breach of licence conditions": ("ICI", [], None, None),
    "Harmful or unlawful online content": ("MCD", ["Harassment", "Impersonation", "Privacy"], None, None),
    "Media fairness and conduct": ("MCD", ["Inaccurate reporting", "Advertising"], None, None),
    "Regulated broadcast or published content": ("MCD", [], None, None),
    "Film classification": ("MCD", [], None, None),
}
PRIORITIES = [("Urgent", 4, 1, 5), ("High", 3, 2, 10), ("Normal", 2, 3, 15), ("Low", 1, 5, 30)]
PROVIDER_TYPES = ["Telecom operator", "ISP", "Cable TV operator", "Broadcaster", "Publisher", "OTT platform", "Other"]
OUTCOMES = ["Upheld", "Partly upheld", "Not upheld", "Referred to another authority", "Withdrawn"]
CLOSURE_REASONS = ["Resolved", "Not within BICMA jurisdiction", "Withdrawn by complainant", "No response from complainant", "Referred"]
TEMPLATES = [
    ("acknowledgement", "Complaint acknowledgement", "complainant", "Complaint {reference} received", "Your complaint \"{subject}\" has been received.\n\nReference number: {reference}\nTrack it at: {tracking_url}\n\nBICMA"),
    ("status_change", "Status update", "complainant", "Update on complaint {reference}", "The status of your complaint {reference} is now: {status}.\n\n{message}\n\nTrack it at: {tracking_url}\n\nBICMA"),
    ("info_request", "Request for information", "complainant", "Information needed: complaint {reference}", "BICMA needs more information to continue with complaint {reference}:\n\n{message}\n\nReply at: {tracking_url}\n\nBICMA"),
    ("closure", "Closure", "complainant", "Complaint {reference} closed", "Your complaint {reference} has been closed.\n\n{message}\n\nBICMA"),
    ("not_within_mandate", "Outside jurisdiction", "complainant", "Complaint {reference}: outside BICMA jurisdiction", "Your complaint {reference} is outside BICMA's jurisdiction and has been closed.\n\n{message}\n\nBICMA"),
    ("stakeholder_review", "Stakeholder notice after initial review", "provider", "Complaint {reference}: BICMA initial review", "BICMA has completed an initial review of complaint {reference} concerning {category}.\n\n{message}\n\nPlease respond to BICMA.\n\nBICMA"),
]


class Command(BaseCommand):
    help = "Idempotent first-run setup: default divisions, categories, settings and the initial Super Administrator."

    def handle(self, *args, **opts):
        from core.models import ClosureReason, EmailTemplate, Outcome, Priority, ProviderType
        if not Division.objects.exists():
            for name, code in DEFAULT_DIVISIONS:
                Division.objects.create(name=name, code=code)
            self.stdout.write("Created BICMA's three divisions (editable in the UI).")
        if not SystemConfiguration.objects.filter(key="dzongkhags_seeded").exists():
            have = {n.lower() for n in Dzongkhag.objects.values_list("name", flat=True)}
            Dzongkhag.objects.bulk_create([Dzongkhag(name=n) for n in DZONGKHAGS if n.lower() not in have])
            SystemConfiguration.objects.create(key="dzongkhags_seeded", value="1", description="Initial Dzongkhag list loaded (one-time)")
            self.stdout.write("Loaded the 20 Dzongkhags. Gewogs are added in the admin UI (Master data > Gewogs).")
        if not Priority.objects.exists():
            for name, rank, resp, resol in PRIORITIES:
                Priority.objects.create(name=name, rank=rank, response_days=resp, resolution_days=resol)
            self.stdout.write("Created default priorities and timelines (placeholders: BICMA to confirm).")
        if not Category.objects.exists():
            divs = {d.code: d for d in Division.objects.all()}
            normal = Priority.objects.filter(name="Normal").first()
            for cat, (code, subs, urban, rural) in DEFAULT_CATEGORIES.items():
                c = Category.objects.create(name=cat, default_division=divs.get(code), urban_division=divs.get(urban) if urban else None,
                                            rural_division=divs.get(rural) if rural else None, default_priority=normal)
                Subcategory.objects.bulk_create([Subcategory(category=c, name=s) for s in subs])
            self.stdout.write("Created default categories (editable in the UI).")
        if not ProviderType.objects.exists():
            ProviderType.objects.bulk_create([ProviderType(name=n) for n in PROVIDER_TYPES])
        if not Outcome.objects.exists():
            Outcome.objects.bulk_create([Outcome(name=n) for n in OUTCOMES])
        if not ClosureReason.objects.exists():
            ClosureReason.objects.bulk_create([ClosureReason(name=n) for n in CLOSURE_REASONS])
        for event, name, recipient, subject, body in TEMPLATES:
            EmailTemplate.objects.get_or_create(event=event, defaults={"name": name, "recipient": recipient, "subject": subject, "body": body})
        SystemConfiguration.objects.get_or_create(
            key="reference_prefix", defaults={"value": "BICMA-CMS", "description": "Prefix of complaint reference numbers"}
        )
        email = os.environ.get("BICMA_ADMIN_EMAIL")
        password = os.environ.get("BICMA_ADMIN_PASSWORD")
        if email and password and not User.objects.filter(role=Role.SUPER_ADMIN).exists():
            User.objects.create_user(email=email, password=password, role=Role.SUPER_ADMIN, is_staff=True)
            self.stdout.write(f"Created initial Super Administrator {email}.")

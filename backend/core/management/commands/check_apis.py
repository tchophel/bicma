from django.core.management.base import BaseCommand

from core import apihealth


class Command(BaseCommand):
    help = "Check that the external APIs (DCRC, ZESt) are reachable and record the result. Run every 5 minutes from cron."

    def handle(self, *args, **opts):
        results = apihealth.check_all()
        for c in results:
            self.stdout.write(f"{c.service}: {'up' if c.ok else 'DOWN'} in {c.latency_ms} ms {c.error}".strip())
        if not results:
            self.stdout.write("No external API is configured.")

from django.core.management.base import BaseCommand

from core import secscan


class Command(BaseCommand):
    help = "Run the automated security checks (dependencies, CI, SonarQube, ZAP) and alert the Administrators about new issues. Daily."

    def handle(self, *args, **opts):
        for key, res in secscan.run_all().items():
            self.stdout.write(f"{key}: {res['state']} {res['summary']}")

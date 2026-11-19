from django.core.management.base import BaseCommand

from complaints.services import deliver
from core.models import NotificationLog


class Command(BaseCommand):
    help = "Retry emails that failed to send (run every few minutes from cron). Gives up after 5 attempts."

    def handle(self, *args, **opts):
        sent = 0
        for entry in NotificationLog.objects.filter(status__in=["failed", "pending"], attempts__lt=5):
            sent += deliver(entry)
        self.stdout.write(f"Retried; {sent} delivered.")

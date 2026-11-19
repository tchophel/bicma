import datetime as dt

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import ApiHealthCheck, ApiLog, EmailLog, SmsLog


class Command(BaseCommand):
    help = "Delete API, email and SMS log rows older than --days (default 90). Audit logs are never touched."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90)

    def handle(self, *args, **opts):
        cutoff = timezone.now() - dt.timedelta(days=opts["days"])
        total = 0
        for model in (ApiLog, EmailLog, SmsLog):
            n, _ = model.objects.filter(created_at__lt=cutoff).delete()
            total += n
        n, _ = ApiHealthCheck.objects.filter(checked_at__lt=cutoff).delete()
        total += n
        self.stdout.write(f"Deleted {total} log rows older than {opts['days']} days.")

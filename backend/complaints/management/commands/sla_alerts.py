import datetime as dt

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Role, User
from complaints.models import OPEN_STATUSES, Complaint, InternalStatus as S
from core.models import Notification, SystemConfiguration
from core.notifications import notify


class Command(BaseCommand):
    help = "Alert officers / Division Heads about due-soon, overdue and untriaged complaints (run hourly from cron). Alerts are sent once per case and kind."

    def _once(self, complaint, kind):
        key = f"/staff/complaints/{complaint.pk}#{kind}"
        return not Notification.objects.filter(link=key).exists(), key

    def handle(self, *args, **opts):
        now = timezone.now()
        triage_days = int(SystemConfiguration.get("triage_period_days", "2") or 2)
        count = 0
        for c in Complaint.objects.filter(internal_status__in=OPEN_STATUSES, paused_at__isnull=True).select_related("assigned_to"):
            heads = list(User.objects.filter(role=Role.FOCAL, is_active=True, division_id=c.division_id))
            targets = ([c.assigned_to] if c.assigned_to else []) + heads
            if c.resolution_due_at and c.resolution_due_at < now:
                kind, msg = "overdue", f"{c.reference} has missed its resolution timeline."
            elif c.resolution_due_at and c.resolution_due_at - now < dt.timedelta(days=2):
                kind, msg = "due_soon", f"{c.reference} is approaching its resolution timeline."
            elif c.internal_status in (S.RECEIVED, S.TRIAGE) and now - c.created_at > dt.timedelta(days=triage_days):
                kind, msg, targets = "untriaged", f"{c.reference} has been waiting for assignment beyond the triage period.", heads
            else:
                continue
            fresh, key = self._once(c, kind)
            if fresh and targets:
                notify(targets, msg, key)
                count += 1
        self.stdout.write(f"{count} alert batches created.")

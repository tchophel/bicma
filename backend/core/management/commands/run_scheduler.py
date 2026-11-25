import logging
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand

log = logging.getLogger(__name__)

# (command, arguments, every N seconds)
JOBS = [
    ("check_apis", [], 300),             # is DCRC / ZESt up? (feeds the graph on Logs > API)
    ("retry_failed_emails", [], 300),    # retry emails that failed to send
    ("sla_alerts", [], 3600),            # due-soon, overdue and untriaged alerts
    ("security_scans", [], 86400),       # dependency, CI, SonarQube and ZAP checks; alerts the Administrators on new issues
    ("compress_resolved_files", [], 86400),  # shrink pictures of resolved complaints, if switched on in Settings > Storage
    ("purge_logs", ["--days", "90"], 86400),
]


def run_due(last_run, now):
    """Run every job whose interval has passed. Returns the names that ran. One failing job never stops the others."""
    ran = []
    for name, args, every in JOBS:
        if now - last_run.get(name, 0) >= every:
            last_run[name] = now
            try:
                call_command(name, *args, verbosity=0)
            except Exception:
                log.exception("Scheduled job %s failed", name)
            ran.append(name)
    return ran


class Command(BaseCommand):
    help = "Long-running scheduler for the background jobs (use where cron or CronJobs are not available)."

    def handle(self, *args, **opts):
        self.stdout.write("Scheduler started.")
        last_run = {}
        while True:
            ran = run_due(last_run, time.time())
            if ran:
                self.stdout.write(f"Ran: {', '.join(ran)}")
            time.sleep(30)

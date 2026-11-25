from django.core.management.base import BaseCommand

from complaints import compress


class Command(BaseCommand):
    help = "Shrink the pictures of resolved and closed complaints to save disk space (skipped when switched off in Settings > Storage)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when the daily job is switched off")

    def handle(self, *args, **opts):
        if not (opts["force"] or compress.enabled()):
            return
        r = compress.run()
        self.stdout.write(f"Checked {r['checked']}, shrunk {r['shrunk']}, saved {r['bytes_saved']} bytes, failed {r['failed']}")

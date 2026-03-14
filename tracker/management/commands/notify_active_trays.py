import time

from django.core.management.base import BaseCommand

from services.notifications.active_tray_notifier import notify_active_trays


class Command(BaseCommand):
    help = "Continuous watcher that posts Telegram alerts for active trays."

    def add_arguments(self, parser):
        parser.add_argument(
            "--loop-seconds",
            type=int,
            default=60,
            help="Polling interval between alert evaluations (seconds).",
        )
        parser.add_argument(
            "--run-once",
            action="store_true",
            help="Send alerts a single time and then exit (useful for cron).",
        )

    def handle(self, *args, **options):
        loop_seconds = max(options["loop_seconds"], 15)
        run_once = options["run_once"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting active tray notifier (loop every {loop_seconds}s, run_once={run_once})"
            )
        )

        while True:
            sent = notify_active_trays()
            if sent:
                self.stdout.write(f"Sent {sent} Telegram tray alert(s).")

            if run_once:
                break

            time.sleep(loop_seconds)

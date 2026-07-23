import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from services.data_storage.repository import purge_heartbeat_events


class Command(BaseCommand):
    help = (
        "Prune heartbeat event logs (TrayHeartbeatEvent) older than the "
        "retention window. Tray status logs (TrayEvent) are never touched."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--weeks",
            type=int,
            default=None,
            help=(
                "Retention window in weeks. Defaults to "
                "settings.TRAY_HEARTBEAT_RETENTION_WEEKS."
            ),
        )
        parser.add_argument(
            "--loop-seconds",
            type=int,
            default=86400,
            help="Polling interval between prunes (seconds). Defaults to daily.",
        )
        parser.add_argument(
            "--run-once",
            action="store_true",
            help="Prune a single time and then exit (useful for cron).",
        )

    def handle(self, *args, **options):
        weeks = options["weeks"]
        if weeks is None:
            weeks = getattr(settings, "TRAY_HEARTBEAT_RETENTION_WEEKS", 6)
        if weeks <= 0:
            raise CommandError("--weeks must be a positive number of weeks")

        loop_seconds = max(options["loop_seconds"], 60)
        run_once = options["run_once"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting heartbeat log pruner (retain {weeks} week(s), "
                f"loop every {loop_seconds}s, run_once={run_once})"
            )
        )

        while True:
            deleted = purge_heartbeat_events(retention_weeks=weeks)
            self.stdout.write(f"Pruned {deleted} heartbeat event log(s).")

            if run_once:
                break

            time.sleep(loop_seconds)

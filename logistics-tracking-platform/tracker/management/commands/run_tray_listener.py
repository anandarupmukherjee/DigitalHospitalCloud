import logging

from django.core.management.base import BaseCommand

from services.data_collection_tray.listener import TrayMQTTListener

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Starts the MQTT listener for MET tray trackers."

    def add_arguments(self, parser):
        parser.add_argument("--broker-host", help="MQTT broker hostname")
        parser.add_argument("--broker-port", type=int, help="MQTT broker port")
        parser.add_argument("--topic", help="Topic/filter to subscribe to")

    def handle(self, *args, **options):
        listener = TrayMQTTListener(
            broker_host=options.get("broker_host"),
            broker_port=options.get("broker_port"),
            topic=options.get("topic"),
        )
        self.stdout.write(self.style.SUCCESS("Tray MQTT listener started. Press CTRL+C to stop."))
        try:
            listener.start()
        except KeyboardInterrupt:
            logger.info("MQTT listener interrupted by user")

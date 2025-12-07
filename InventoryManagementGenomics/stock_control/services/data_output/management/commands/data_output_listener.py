import json
import logging
import signal
import sys
from difflib import SequenceMatcher

from django.conf import settings
from django.core.management.base import BaseCommand

try:
    import paho.mqtt.client as mqtt
except ImportError as exc:  # pragma: no cover - surfaces during misconfiguration
    raise SystemExit(
        "paho-mqtt is required for the data_output service. "
        "Install it via `pip install paho-mqtt`."
    ) from exc

from services.data_storage.models import Product, StockInEntry


logger = logging.getLogger(__name__)


class ProductMatcher:
    """Utility to find fuzzy matches for product names and aliases."""

    def __init__(self, threshold: float):
        self.threshold = threshold

    def _score(self, query: str, candidate: str) -> float:
        return SequenceMatcher(None, query.lower(), candidate.lower()).ratio()

    def _combined_score(self, query: str, product: Product) -> float:
        """
        Compute a score that considers both the formal product name and
        the alias. The match is taken as the better of the two so that
        close matches on either field are recognised.
        """
        name_score = self._score(query, product.name or "")
        alias_score = self._score(query, product.alias or "")
        return max(name_score, alias_score)

    def find(self, query: str):
        if not query:
            return None, 0.0

        best_match = None
        best_score = 0.0

        # Consider both name and alias for fuzzy matching so that
        # partial or off‑brand descriptions can still find a sensible
        # candidate.
        for product in Product.objects.all().only("id", "name", "alias", "product_code"):
            score = self._combined_score(query, product)
            if score > best_score:
                best_match = product
                best_score = score

        if best_match and best_score >= self.threshold:
            return best_match, best_score
        return None, best_score


class Command(BaseCommand):
    help = (
        "Listen to HiveMQ topic 'lobby/lift/packages/check', "
        "perform a fuzzy lookup for product names, "
        "and respond on 'lobby/lift/packages/response'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default=getattr(settings, "DATA_OUTPUT_MQTT_HOST", "broker.hivemq.com"),
            help="MQTT broker host (default: broker.hivemq.com)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=getattr(settings, "DATA_OUTPUT_MQTT_PORT", 1883),
            help="MQTT broker port (default: 1883)",
        )
        parser.add_argument(
            "--threshold",
            type=float,
            default=getattr(settings, "DATA_OUTPUT_FUZZY_THRESHOLD", 0.6),
            help="Minimum SequenceMatcher ratio (0-1) required to treat a product as existing.",
        )

    def handle(self, *args, **options):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

        host = options["host"]
        port = options["port"]
        check_topic = settings.DATA_OUTPUT_MQTT_CHECK_TOPIC
        response_topic = settings.DATA_OUTPUT_MQTT_RESPONSE_TOPIC
        print_topic = getattr(
            settings,
            "DATA_OUTPUT_MQTT_PRINT_TOPIC",
            "lift/lobby/packages/print",
        )
        threshold = options["threshold"]
        matcher = ProductMatcher(threshold)

        client = mqtt.Client()
        client.enable_logger(logger)

        def _graceful_exit(*_args):
            logger.info("Shutting down MQTT listener...")
            client.disconnect()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _graceful_exit)
        signal.signal(signal.SIGINT, _graceful_exit)

        def on_connect(_client, _userdata, _flags, rc):
            if rc == 0:
                logger.info("Connected to MQTT broker %s:%s", host, port)
                _client.subscribe(check_topic, qos=1)
                _client.subscribe(print_topic, qos=1)
                logger.info("Subscribed to %s and %s", check_topic, print_topic)
            else:
                logger.error("Failed to connect to MQTT broker: rc=%s", rc)

        def on_message(_client, _userdata, msg):
            raw_payload = msg.payload.decode("utf-8").strip()
            logger.info("Received payload on %s: %s", msg.topic, raw_payload)

            if msg.topic == check_topic:
                product_name = self._extract_product_name(raw_payload)

                product, score = matcher.find(product_name)
                match_found = bool(
                    product
                    and score
                    >= getattr(settings, "DATA_OUTPUT_RESPONSE_THRESHOLD", 0.8)
                )
                product_payload = (
                    {
                        "id": product.id,
                        "name": product.name,
                        "product_code": product.product_code,
                        "alias": product.alias,
                        "barcode_value": product.product_code,
                        # Always expose a numeric QR code value. Ensure that
                        # a qr_numeric_code exists; if not, persist one.
                        "qrcode_value": self._ensure_numeric_qr(product),
                    }
                    if match_found
                    else None
                )
                response = {
                    "requested_name": product_name,
                    "match_found": match_found,
                    "match_score": round(score * 100, 2),
                    "product": product_payload,
                    "message": "Product found" if match_found else "Product not found",
                }

                payload = json.dumps(response)
                _client.publish(response_topic, payload, qos=1, retain=False)
                logger.info(
                    "Published response to %s (match_found=%s, score=%s)",
                    response_topic,
                    response["match_found"],
                    response["match_score"],
                )
            elif msg.topic == print_topic:
                self._handle_print_message(raw_payload)

        client.on_connect = on_connect
        client.on_message = on_message

        logger.info(
            "Starting data_output listener | host=%s port=%s threshold=%s",
            host,
            port,
            threshold,
        )

        client.connect(host, port)
        client.loop_forever()

    @staticmethod
    def _extract_product_name(raw_payload: str) -> str:
        """Interpret the inbound payload and return the product name string."""
        if not raw_payload:
            return ""

        try:
            data = json.loads(raw_payload)
            if isinstance(data, dict):
                ordered_keys = (
                    "combinedText",
                    "product_name",
                    "name",
                    "product",
                    "query",
                )
                for key in ordered_keys:
                    value = data.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()

                texts = data.get("texts")
                if isinstance(texts, list):
                    for entry in texts:
                        if isinstance(entry, str) and entry.strip():
                            return entry.strip()
            elif isinstance(data, str):
                return data.strip()
        except json.JSONDecodeError:
            pass

        return raw_payload

    @staticmethod
    def _ensure_numeric_qr(product: Product) -> str:
        """
        Ensure the product has a numeric QR identifier and return it as
        a string for use in MQTT payloads.
        """
        if not getattr(product, "qr_numeric_code", None):
            product.save(update_fields=None)
        return str(product.qr_numeric_code)

    @staticmethod
    def _handle_print_message(raw_payload: str) -> None:
        """
        Handle messages from the print topic. Each message represents a
        request to generate QR codes for a product. We record these as
        stock-in expectations that can later be reconciled with actual
        registrations.
        """
        if not raw_payload:
            return

        try:
            data = json.loads(raw_payload)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON on print topic: %s", raw_payload)
            return

        timestamp_str = data.get("timestamp")
        product_code = data.get("productCode") or data.get("product_code")
        product_name = (
            data.get("productName")
            or (data.get("product") or {}).get("name")
            or ""
        )

        if not product_code and not product_name:
            logger.warning("Print message missing product identifiers: %s", raw_payload)
            return

        # Parse timestamp if provided, otherwise fall back to now.
        from datetime import datetime
        from django.utils.timezone import make_aware, now as tz_now

        printed_at = tz_now()
        if timestamp_str:
            try:
                parsed = datetime.fromisoformat(timestamp_str)
                if parsed.tzinfo is None:
                    printed_at = make_aware(parsed)
                else:
                    printed_at = parsed
            except Exception:
                logger.warning("Could not parse timestamp '%s'", timestamp_str)

        # Prefer lookup by product code; fall back to fuzzy matching by name.
        product = None
        if product_code:
            product = Product.objects.filter(product_code__iexact=product_code).first()
        if not product and product_name:
            matcher = ProductMatcher(
                getattr(settings, "DATA_OUTPUT_FUZZY_THRESHOLD", 0.6)
            )
            product, _score = matcher.find(product_name)

        if not product:
            logger.warning(
                "No matching Product found for print message (code=%s, name=%s)",
                product_code,
                product_name,
            )
            return

        # Always use the numeric QR identifier we control.
        qrcode_value = str(
            getattr(product, "qr_numeric_code", None) or Command._ensure_numeric_qr(product)
        )

        entry, created = StockInEntry.objects.get_or_create(
            product=product,
            defaults={
                "product_code": product.product_code,
                "product_name": product.name,
                "qrcode_value": qrcode_value,
                "first_printed_at": printed_at,
                "last_printed_at": printed_at,
                "print_count": 1,
            },
        )

        if not created:
            entry.last_printed_at = printed_at
            entry.print_count += 1
            # Keep descriptive fields in sync in case product naming changed.
            entry.product_code = product.product_code
            entry.product_name = product.name
            entry.qrcode_value = qrcode_value
            entry.save(
                update_fields=[
                    "last_printed_at",
                    "print_count",
                    "product_code",
                    "product_name",
                    "qrcode_value",
                ]
            )

import json
import machine
import network
import time
from machine import Pin, PWM
from pico_lcd_13 import LCD_1inch3  # Make sure this file is uploaded
from umqttsimple import MQTTClient

# =======================
# Global MQTT client
# =======================
client = None

# =======================
# LCD & Backlight setup
# =======================
pwm = PWM(Pin(13))        # Backlight pin for 1.3" LCD
pwm.freq(1000)
pwm.duty_u16(32768)       # Medium brightness

lcd = LCD_1inch3()
lcd.fill(lcd.white)
lcd.show()

# Buttons (active LOW, with pull-ups)
btn_a = Pin(15, Pin.IN, Pin.PULL_UP)   # ON
btn_b = Pin(17, Pin.IN, Pin.PULL_UP)   # OFF


def display_msg(line1="", line2="", line3=""):
    """Helper to draw up to 3 lines on the LCD."""
    lcd.fill(lcd.white)
    if line1:
        lcd.text(line1, 10, 40, lcd.blue)
    if line2:
        lcd.text(line2, 10, 80, lcd.green)
    if line3:
        lcd.text(line3, 10, 120, lcd.red)
    lcd.show()


# =======================
# Wi-Fi / MQTT config
# =======================
ssid = "ZTE_A3CF2C"        # <-- change if needed
password = "52648656"      # <-- change if needed

PICO_ID = "PICO-001"

DEFAULT_LOCATION_LABEL = "IfM"
DEFAULT_TRAY_ID = "TRAY-IFM"
DEFAULT_LATITUDE = 52.20957620134866
DEFAULT_LONGITUDE = 0.08741983954533321

# Mutable config populated via MQTT configure topic
location_label = DEFAULT_LOCATION_LABEL
tray_id = DEFAULT_TRAY_ID
latitude = DEFAULT_LATITUDE
longitude = DEFAULT_LONGITUDE

mqtt_server = "broker.hivemq.com"   # change to your broker if needed
mqtt_port = 1883

# MQTT expects bytes for client_id and topics for this umqtt
CLIENT_ID = ("ReadyBox_%s" % PICO_ID).encode()
CONFIG_TOPIC = b"MET/hospital/sensors/configure"

# Config persistence file
CONFIG_FILE = "tray_config.json"


def sensor_topic():
    """Dynamic publish topic based on current tray_id."""
    return ("MET/hospital/sensors/%s" % tray_id).encode()


# =======================
# Config persistence
# =======================
def load_config():
    """Load tray/location config from flash if available."""
    global tray_id, location_label, latitude, longitude
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        tray_id = cfg.get("tray_id", tray_id)
        location_label = cfg.get("location_label", location_label)
        latitude = cfg.get("latitude", latitude)
        longitude = cfg.get("longitude", longitude)
        print("Loaded config:", cfg)
        display_msg("Config loaded", location_label, tray_id)
    except OSError:
        # File does not exist; stick to defaults
        print("No config file, using defaults")
        display_msg("No config", "Using defaults")


def save_config():
    """Persist current tray/location config to flash."""
    cfg = {
        "tray_id": tray_id,
        "location_label": location_label,
        "latitude": latitude,
        "longitude": longitude,
    }
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f)
        print("Saved config:", cfg)
        display_msg("Config saved", location_label, tray_id)
    except Exception as exc:
        print("Config save error:", exc)
        display_msg("Save error", str(exc)[:16])


# =======================
# Wi-Fi connect
# =======================
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        display_msg("WiFi", "Connecting...")
        wlan.connect(ssid, password)
        attempt = 0
        while not wlan.isconnected():
            attempt += 1
            print("Waiting for WiFi... Attempt", attempt)
            time.sleep(1)

    ip = wlan.ifconfig()[0]
    display_msg("WiFi Connected", ip)
    print("WiFi IP:", ip)
    return wlan


# =======================
# MQTT helpers
# =======================
def handle_config_message(msg):
    """Update tray metadata when config payload targets this Pico, then persist."""
    global tray_id, location_label, latitude, longitude
    try:
        payload = json.loads(msg.decode("utf-8"))
    except Exception as exc:
        print("Config decode error:", exc)
        display_msg("Config error", str(exc)[:16])
        return

    target = payload.get("pico_id")
    if target and target != PICO_ID:
        print("Ignoring config for", target)
        return

    tray_id = payload.get("tray_id") or tray_id
    location_label = (
        payload.get("location_label")
        or payload.get("location_name")
        or location_label
    )
    latitude = payload.get("latitude", latitude)
    longitude = payload.get("longitude", longitude)

    display_msg("Config updated", location_label, tray_id)
    print("Config applied:", payload)
    save_config()


def mqtt_callback(topic, msg):
    # Topic and msg are bytes here
    if topic == CONFIG_TOPIC:
        handle_config_message(msg)
    else:
        print("MQTT message:", topic, msg)


def setup():
    """Connect Wi-Fi and MQTT, return connected client."""
    global client
    connect_wifi()
    load_config()

    client = MQTTClient(
        CLIENT_ID,         # bytes
        mqtt_server,       # string hostname is fine
        port=mqtt_port
    )
    client.set_callback(mqtt_callback)
    print("Connecting to MQTT...")

    attempt = 0
    while True:
        try:
            client.connect()
            print("MQTT Connected")
            client.subscribe(CONFIG_TOPIC)
            print("Subscribed to", CONFIG_TOPIC)
            display_msg("MQTT Connected", location_label)
            break
        except Exception as e:
            attempt += 1
            print("MQTT connect failed (%d): %s" % (attempt, e))
            display_msg("MQTT FAIL", "Retry %d" % attempt)
            time.sleep(5)

    return client


def mqtt_reconnect():
    """Try to reconnect MQTT if connection drops."""
    global client
    attempt = 0
    while True:
        try:
            client.connect()
            client.subscribe(CONFIG_TOPIC)
            display_msg("MQTT Reconnected", location_label)
            print("MQTT Reconnected")
            break
        except Exception as e:
            attempt += 1
            print("Reconnect failed (%d): %s" % (attempt, e))
            display_msg("MQTT FAIL", "Retry %d" % attempt)
            time.sleep(5)


def publish_json_status(client, state):
    """
    Publish JSON payload with tray/location metadata and status.
    state: "on" or "off"
    """
    payload = {
        "tray_id": tray_id,
        "status": state,
        "latitude": latitude,
        "longitude": longitude,
        "location_label": location_label,
    }

    # umqttsimple.publish wants bytes for msg
    msg = json.dumps(payload).encode("utf-8")
    topic = sensor_topic()
    print("Publishing to", topic, ":", msg)

    try:
        client.publish(topic, msg)
        display_msg("Sent", state.upper(), location_label)
    except Exception as e:
        print("Publish failed:", e)
        display_msg("MQTT ERROR", str(e))
        mqtt_reconnect()


# =======================
# Main loop
# =======================
def loop(client):
    print("Main loop started")
    display_msg("READYBOX", location_label)

    # For edge detection (avoid spamming while button held)
    last_a = 1  # pull-up: 1 = not pressed
    last_b = 1

    while True:
        # Keep MQTT alive / process any incoming messages
        try:
            client.check_msg()
        except Exception as e:
            print("MQTT dropped:", e)
            display_msg("MQTT Lost", "Reconnecting...")
            mqtt_reconnect()

        cur_a = btn_a.value()
        cur_b = btn_b.value()

        # BTN-A (active LOW) → ON (edge: 1 -> 0)
        if cur_a == 0 and last_a == 1:
            publish_json_status(client, "on")
            time.sleep(0.3)  # debounce

        # BTN-B (active LOW) → OFF (edge: 1 -> 0)
        if cur_b == 0 and last_b == 1:
            publish_json_status(client, "off")
            time.sleep(0.3)  # debounce

        last_a = cur_a
        last_b = cur_b

        time.sleep(0.05)


# =======================
# Start system
# =======================
display_msg("READYBOX", location_label)
client = setup()
loop(client)


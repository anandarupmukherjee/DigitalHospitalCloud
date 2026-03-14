# Logistics Sample Tracker

A modular Django project that renders tray tracker locations on a Leaflet map and listens to MQTT updates from the `MET/hospital/sensors/#` topic on the public HiveMQ broker. Incoming MQTT messages trigger a blinking marker on the map and are persisted for audit and replay.

## Features

- Dashboard map powered by Leaflet with automatic refresh and blinking markers for active trays.
- MQTT ingestion service stored under `services/data_collection_tray`.
- Data persistence helpers in `services/data_storage` that record tray state, geolocation, and event history snapshots.
- Raspberry Pi Pico firmware now lives outside the Django project under `hardware/data_collection_sensor` so it can be flashed or versioned independently.
- Container-ready Dockerfile and Compose setup for local development or deployment.
- Tray activity analytics page with range filters (day/week/month/year), event logs, and Chart.js summaries of collection durations.
- Configure trays screen that lets managers push Pico metadata (tray/location/latitude/longitude) over MQTT config topics.
- Role-aware user management with login, logout, password change, and manager/staff roles for access control.
- Django admin registration for manual inspection of tray records.

## Project layout

```
Logistics_Sample_Tracker/
├── logistics_tracker/        # Django project settings
├── tracker/                  # Application with models, views, API, and management command
├── services/
│   ├── data_collection_tray/ # MQTT listener implementation
│   └── data_storage/         # Database helper functions
├── hardware/
│   └── data_collection_sensor/ # Pico W firmware, LCD helpers, and UF2 images
├── templates/                # Base, dashboard, tray history, auth, etc.
├── static/                   # CSS plus dashboard/history JavaScript assets
└── manage.py
```

## Getting started

1. *(Optional)* Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Apply database migrations:
   ```bash
   python manage.py migrate
   ```
4. Create a Django superuser so you can log in:
   ```bash
   python manage.py createsuperuser
   ```
5. Run the development server:
   ```bash
   python manage.py runserver
   ```
6. In a separate terminal, start the MQTT listener:
   ```bash
   python manage.py run_tray_listener
   ```

### Running with Docker

1. Copy the sample environment file and tweak it as needed:
   ```bash
   cp .env.example .env
   ```
   Update `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS` before deploying anywhere public.
2. Build and run the containers:
   ```bash
   docker compose up --build
   ```
   Compose now launches three services: `web` (Gunicorn serving Django), `listener` (runs `python manage.py run_tray_listener`), and `notifier` (runs `python manage.py notify_active_trays`). The shared entrypoint applies migrations before any service starts; only the web service runs `collectstatic`. Static files are mounted to a named volume so they persist between rebuilds.
3. Visit [http://localhost:8000](http://localhost:8000) in your browser. Use `Ctrl+C` to stop the stack or `docker compose down` to tear it down completely.

### Data collection sensor firmware

The sensor firmware that runs on the Raspberry Pi Pico W has been moved out of the Django project tree into `hardware/data_collection_sensor/`. Copy that folder to your MicroPython workspace (or mount it via Thonny/Mu), flash `universal_flash_nuke.uf2` if you need to erase the device, and then upload `pico_client.py`, `pico_lcd_13.py`, and `umqttsimple.py` after flashing `RPI_PICO_W-20250415-v1.25.0.uf2`.

The listener connects to `broker.hivemq.com` by default and subscribes to `MET/hospital/sensors/#`. Override the broker or topic via environment variables (`MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`, `MQTT_TOPIC`) or by passing `--broker-host`, `--broker-port`, or `--topic` flags to the management command.

### Roles and permissions

- **Managers** (or superusers) can access the Dashboard, Tray Details analytics, and User Management. They can invite additional users and choose the Manager/Staff role at creation time.
- **Staff** accounts are limited to the Dashboard to monitor live activity but cannot open analytics, configure trays, or manage users.

Use the User Management page (navigation bar) to provision additional accounts after logging in as a manager.

Messages should be JSON and are expected to contain at least a `tray_id` plus optional `location`/`status` fields, for example:

```json
{
  "tray_id": "TRAY-42",
  "status": "on",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "location_label": "ER Intake"
}
```

Each update is stored in the `TrayStatus` model along with activation/deactivation timestamps and also logged in `TrayEvent` for detailed history. The dashboard polls `/api/tray-status/` every five seconds and updates the map markers accordingly, while the Tray Details page surfaces historical analytics for operations managers. User management is restricted to the Manager role, whereas Staff accounts are limited to the dashboard view.

### Telegram tray alerts

To keep operations updated, a notifier now posts to a Telegram channel whenever trays stay active. Recommended flow:

1. Create a Telegram channel such as `@logistics_tray_alerts`, invite your stakeholders, and add your bot as an administrator so it can post updates.
2. Create a bot via [@BotFather](https://t.me/BotFather) and grab the token plus the channel chat ID (prefix public channels with `@` or use the numeric ID for private channels).
3. Set these variables in `.env` (or your deployment secrets):
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_CHAT_ID=@logistics_tray_alerts
   TRAY_ALERT_INTERVAL_MINUTES=30
   ```
   `TRAY_ALERT_INTERVAL_MINUTES` is optional (defaults to 30 minutes).
4. `docker compose up -d notifier` (already part of `docker compose up`) runs `python manage.py notify_active_trays`, which evaluates active trays every minute and posts a reminder message every 30 minutes until the tray deactivates.

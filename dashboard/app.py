import os
import logging
import yaml
import docker
from flask import Flask, render_template, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get("APPS_CONFIG", "apps.yaml")
APP_HOST = os.environ.get("APP_HOST", "localhost")


def load_apps():
    if not os.path.exists(CONFIG_PATH):
        logger.warning("Config file %s not found", CONFIG_PATH)
        return []
    with open(CONFIG_PATH, "r") as f:
        data = yaml.safe_load(f) or {}
    apps = data.get("apps", [])
    normalized = []
    for app_cfg in apps:
        url = app_cfg.get("url")
        port = app_cfg.get("port")
        path = app_cfg.get("path", "")
        if not url and port:
            url = f"http://{APP_HOST}:{port}{path}"
        normalized.append(
            {
                "id": app_cfg.get("id", app_cfg.get("name", "app")).lower(),
                "name": app_cfg.get("name", "App"),
                "description": app_cfg.get("description", ""),
                "port": port,
                "path": path,
                "url": url,
                "container": app_cfg.get("container"),
                "check_status": app_cfg.get("check_status", True),
            }
        )
    return normalized


def create_docker_client():
    try:
        client = docker.from_env()
        client.ping()
        return client, None
    except Exception as exc:
        logger.warning("Docker not reachable: %s", exc)
        return None, str(exc)


docker_client, docker_error = create_docker_client()
APPS = load_apps()


def get_status(app_cfg):
    if not app_cfg.get("check_status", True):
        return {"state": "disabled", "details": "status checks disabled"}
    if not docker_client:
        return {"state": "unknown", "details": docker_error or "docker unavailable"}
    container_name = app_cfg.get("container")
    if not container_name:
        return {"state": "unknown", "details": "no container configured"}
    try:
        container = docker_client.containers.get(container_name)
        return {"state": container.status, "details": ""}
    except docker.errors.NotFound:
        return {"state": "stopped", "details": "container not running"}
    except Exception as exc:
        return {"state": "error", "details": str(exc)}


@app.route("/")
@app.route("/dashboard/")
@app.route("/dashboard")
def index():
    status_map = {app_cfg["id"]: get_status(app_cfg) for app_cfg in APPS}
    return render_template("index.html", apps=APPS, status_map=status_map)


@app.route("/api/status")
@app.route("/dashboard/api/status")
def status_api():
    return jsonify({app_cfg["id"]: get_status(app_cfg) for app_cfg in APPS})


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "apps": len(APPS)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

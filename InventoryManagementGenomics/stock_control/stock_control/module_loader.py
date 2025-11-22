import os
from functools import lru_cache

import yaml

MODULE_REGISTRY = {
    "inventory_core": {
        "app": "inventory",
        "optional": False,
        "depends_on": [],
        "description": "Core inventory management (products, withdrawals, stock).",
    },
    "purchase_orders": {
        "app": "solutions.purchase_orders",
        "optional": True,
        "depends_on": ["inventory_core"],
        "description": "Record, track, and complete purchase orders.",
    },
    "quality_control": {
        "app": "solutions.quality_control",
        "optional": True,
        "depends_on": ["inventory_core"],
        "description": "Quality control testing and audit trail.",
    },
    "analytics": {
        "app": "solutions.analytics",
        "optional": True,
        "depends_on": ["inventory_core"],
        "description": "Reporting, forecasting, and withdrawal analytics.",
    },
    "location_tracking": {
        "app": "solutions.location_tracking",
        "optional": True,
        "depends_on": ["inventory_core"],
        "description": "Allocate and track inventory across locations.",
    },
}


def _load_config():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "module_config.yaml")
    try:
        with open(config_path, "r") as handle:
            return yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}


@lru_cache(maxsize=1)
def load_enabled_modules():
    raw_config = _load_config()
    configured_modules = raw_config.get("modules", {})
    modules = {}

    for name, meta in MODULE_REGISTRY.items():
        override = configured_modules.get(name, {})
        if meta.get("optional", True):
            enabled = override.get("enabled", True)
        else:
            enabled = True

        if any(
            not modules.get(dep, {}).get("enabled")
            for dep in meta.get("depends_on", [])
        ):
            enabled = False

        modules[name] = {
            **meta,
            "enabled": bool(enabled),
        }

    return modules


def enabled_apps():
    modules = load_enabled_modules()
    return [
        meta["app"]
        for meta in modules.values()
        if meta["enabled"] and meta.get("app")
    ]


def module_flags():
    modules = load_enabled_modules()
    return {name: meta["enabled"] for name, meta in modules.items()}

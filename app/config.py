"""Persistent user settings: device selection, model size, calls folder.
Stored outside the app folder so they survive the app folder being rebuilt."""

import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".ascolto_win" / "config.json"

DEFAULT_CONFIG = {
    "mic_device_index": None,      # None = system default microphone
    "system_device_index": None,   # None = system default speaker's loopback
    "model_size": "medium",
    "calls_root": str(Path.home() / "Claude" / "calls"),
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return {**DEFAULT_CONFIG, **data}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")

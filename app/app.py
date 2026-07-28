"""
Ascolto-for-Windows: tray-icon meeting recorder.

Manual trigger only (tray icon click or Ctrl+Shift+R hotkey) -- no
auto-detection of meeting apps, per the project brief's decision to keep
this simple since it's used occasionally, not run 24/7. Ctrl+Shift+P
pauses/resumes mid-call without ending it.

Flow: click/hotkey to start -> dual WASAPI capture (mic + system audio) ->
click/hotkey to stop -> local GPU transcription -> call.md + journal.jsonl
written to <calls folder>/<timestamp>/.
"""

import os
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

import keyboard
import pystray
from PIL import Image, ImageDraw

import config as config_module
from audio_capture import CallRecorder
from journal import append_event
import transcriber
from settings_window import open_settings_window

START_HOTKEY = "ctrl+shift+r"
PAUSE_HOTKEY = "ctrl+shift+p"

STATE_LOADING = "loading"
STATE_IDLE = "idle"
STATE_RECORDING = "recording"
STATE_PAUSED = "paused"
STATE_TRANSCRIBING = "transcribing"

ICON_COLORS = {
    STATE_LOADING: (150, 150, 150),
    STATE_IDLE: (60, 140, 60),
    STATE_RECORDING: (200, 40, 40),
    STATE_PAUSED: (230, 150, 30),
    STATE_TRANSCRIBING: (40, 100, 200),
}


class App:
    def __init__(self):
        self.state = STATE_LOADING
        self.lock = threading.Lock()
        self.model = None
        self.recorder = None
        self.current_out_dir = None
        self.call_start_time = None

        self.config = config_module.load_config()
        self.calls_root = Path(self.config["calls_root"])
        self.calls_root.mkdir(parents=True, exist_ok=True)

        self.icon = pystray.Icon(
            "ascolto-win",
            icon=self._make_icon_image(STATE_LOADING),
            title="Ascolto (loading model...)",
            menu=pystray.Menu(
                pystray.MenuItem(self._primary_label, self._on_primary_action, default=True),
                pystray.MenuItem("Stop Recording", self._on_stop_action, enabled=self._stop_enabled),
                pystray.MenuItem("Settings...", self._on_settings, enabled=self._settings_enabled),
                pystray.MenuItem("Open Calls Folder", self._on_open_folder),
                pystray.MenuItem("Quit", self._on_quit),
            ),
        )

    # ---------- icon/menu helpers ----------

    def _make_icon_image(self, state: str) -> Image.Image:
        color = ICON_COLORS[state]
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((8, 8, 56, 56), fill=color)
        return img

    def _primary_label(self, icon):
        if self.state == STATE_LOADING:
            return "Loading model..."
        if self.state == STATE_RECORDING:
            return "Pause Recording"
        if self.state == STATE_PAUSED:
            return "Resume Recording"
        if self.state == STATE_TRANSCRIBING:
            return "Transcribing..."
        return "Start Recording"

    def _stop_enabled(self, item):
        return self.state in (STATE_RECORDING, STATE_PAUSED)

    def _settings_enabled(self, item):
        return self.state == STATE_IDLE

    def _set_state(self, state: str, title: str = None):
        self.state = state
        self.icon.icon = self._make_icon_image(state)
        self.icon.title = title or f"Ascolto ({state})"
        self.icon.update_menu()

    # ---------- menu actions ----------

    def _on_primary_action(self, icon, item):
        with self.lock:
            if self.state == STATE_IDLE:
                self._start_recording_locked()
            elif self.state == STATE_RECORDING:
                self._pause_recording_locked()
            elif self.state == STATE_PAUSED:
                self._resume_recording_locked()

    def _on_stop_action(self, icon, item):
        with self.lock:
            if self.state in (STATE_RECORDING, STATE_PAUSED):
                self._stop_recording_locked()

    def _on_settings(self, icon, item):
        if self.state != STATE_IDLE:
            return
        threading.Thread(target=self._open_settings_thread, daemon=True).start()

    def _on_open_folder(self, icon, item):
        self.calls_root.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self.calls_root))

    def _on_quit(self, icon, item):
        if self.state in (STATE_RECORDING, STATE_PAUSED):
            self.stop_recording()
        self.icon.stop()

    # ---------- hotkeys (start/stop and pause/resume are independent) ----------

    def toggle_recording(self):
        with self.lock:
            if self.state == STATE_IDLE:
                self._start_recording_locked()
            elif self.state in (STATE_RECORDING, STATE_PAUSED):
                self._stop_recording_locked()

    def toggle_pause(self):
        with self.lock:
            if self.state == STATE_RECORDING:
                self._pause_recording_locked()
            elif self.state == STATE_PAUSED:
                self._resume_recording_locked()

    def stop_recording(self):
        with self.lock:
            if self.state in (STATE_RECORDING, STATE_PAUSED):
                self._stop_recording_locked()

    # ---------- state transitions (call only while holding self.lock) ----------

    def _start_recording_locked(self):
        self.call_start_time = datetime.now(timezone.utc)
        out_dir = self.calls_root / self.call_start_time.strftime("%Y-%m-%d-%H%M%S")
        self.current_out_dir = out_dir
        self.recorder = CallRecorder(
            out_dir,
            mic_device_index=self.config.get("mic_device_index"),
            system_device_index=self.config.get("system_device_index"),
        )
        try:
            self.recorder.start()
        except Exception as e:
            append_event(out_dir, "error", stage="start_recording", message=str(e))
            self.icon.notify(f"Failed to start recording: {e}")
            return
        append_event(
            out_dir, "recording_started",
            mic_device=self.recorder.mic_device_name,
            system_device=self.recorder.system_device_name,
        )
        self._set_state(STATE_RECORDING, title="Ascolto (recording...)")

    def _pause_recording_locked(self):
        try:
            self.recorder.pause()
        except Exception as e:
            append_event(self.current_out_dir, "error", stage="pause_recording", message=str(e))
            return
        append_event(self.current_out_dir, "recording_paused")
        self._set_state(STATE_PAUSED, title="Ascolto (paused)")

    def _resume_recording_locked(self):
        try:
            self.recorder.resume()
        except Exception as e:
            append_event(self.current_out_dir, "error", stage="resume_recording", message=str(e))
            return
        append_event(self.current_out_dir, "recording_resumed")
        self._set_state(STATE_RECORDING, title="Ascolto (recording...)")

    def _stop_recording_locked(self):
        recorder = self.recorder
        out_dir = self.current_out_dir
        start_time = self.call_start_time
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        try:
            recorder.stop()
        except Exception as e:
            append_event(out_dir, "error", stage="stop_recording", message=str(e))

        append_event(out_dir, "recording_stopped", duration_seconds=round(duration, 1))
        self._set_state(STATE_TRANSCRIBING, title="Ascolto (transcribing...)")

        meta = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "mic_device": recorder.mic_device_name,
            "system_device": recorder.system_device_name,
        }
        threading.Thread(target=self._transcribe_in_background, args=(out_dir, meta), daemon=True).start()

    def _transcribe_in_background(self, out_dir: Path, meta: dict):
        try:
            transcriber.transcribe_call(self.model, out_dir, meta)
            self.icon.notify(f"Call transcribed: {out_dir.name}")
        except Exception as e:
            append_event(out_dir, "error", stage="transcription", message=str(e), traceback=traceback.format_exc())
            self.icon.notify(f"Transcription failed: {e}")
        finally:
            with self.lock:
                self._set_state(STATE_IDLE, title="Ascolto (idle)")

    # ---------- settings ----------

    def _open_settings_thread(self):
        open_settings_window(self.config, self._on_settings_saved)

    def _on_settings_saved(self, new_config: dict):
        model_changed = new_config["model_size"] != self.config.get("model_size")
        self.config = new_config
        config_module.save_config(self.config)

        self.calls_root = Path(self.config["calls_root"])
        self.calls_root.mkdir(parents=True, exist_ok=True)

        if model_changed:
            with self.lock:
                self._set_state(STATE_LOADING, title="Ascolto (reloading model...)")
            threading.Thread(target=self._load_model_in_background, daemon=True).start()

    # ---------- model loading ----------

    def _load_model_in_background(self):
        self.model = transcriber.load_model(self.config.get("model_size", "medium"))
        with self.lock:
            self._set_state(STATE_IDLE, title="Ascolto (idle)")

    def run(self):
        keyboard.add_hotkey(START_HOTKEY, self.toggle_recording)
        keyboard.add_hotkey(PAUSE_HOTKEY, self.toggle_pause)
        threading.Thread(target=self._load_model_in_background, daemon=True).start()
        self.icon.run()


if __name__ == "__main__":
    App().run()

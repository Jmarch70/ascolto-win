"""
Ascolto-for-Windows, Phase 1: tray-icon meeting recorder.

Manual trigger only (tray icon click or Ctrl+Shift+R hotkey) -- no
auto-detection of meeting apps, per the project brief's decision to keep
this simple since it's used occasionally, not run 24/7.

Flow: click/hotkey to start -> dual WASAPI capture (mic + system audio) ->
click/hotkey to stop -> local GPU transcription -> call.md + journal.jsonl
written to ~/Claude/calls/<timestamp>/.
"""

import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import keyboard
import pystray
from PIL import Image, ImageDraw

from audio_capture import CallRecorder
from journal import append_event
import transcriber

CALLS_ROOT = Path.home() / "Claude" / "calls"
HOTKEY = "ctrl+shift+r"
MODEL_SIZE = "medium"

STATE_LOADING = "loading"
STATE_IDLE = "idle"
STATE_RECORDING = "recording"
STATE_TRANSCRIBING = "transcribing"

ICON_COLORS = {
    STATE_LOADING: (150, 150, 150),
    STATE_IDLE: (60, 140, 60),
    STATE_RECORDING: (200, 40, 40),
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

        self.icon = pystray.Icon(
            "ascolto-win",
            icon=self._make_icon_image(STATE_LOADING),
            title="Ascolto (loading model...)",
            menu=pystray.Menu(
                pystray.MenuItem(self._menu_label, self._on_menu_toggle, default=True),
                pystray.MenuItem("Open Calls Folder", self._on_open_folder),
                pystray.MenuItem("Quit", self._on_quit),
            ),
        )

    def _make_icon_image(self, state: str) -> Image.Image:
        color = ICON_COLORS[state]
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((8, 8, 56, 56), fill=color)
        return img

    def _menu_label(self, icon):
        if self.state == STATE_LOADING:
            return "Loading model..."
        if self.state == STATE_RECORDING:
            return "Stop Recording"
        if self.state == STATE_TRANSCRIBING:
            return "Transcribing..."
        return "Start Recording"

    def _set_state(self, state: str, title: str = None):
        self.state = state
        self.icon.icon = self._make_icon_image(state)
        self.icon.title = title or f"Ascolto ({state})"
        self.icon.update_menu()

    def _on_menu_toggle(self, icon, item):
        self.toggle_recording()

    def _on_open_folder(self, icon, item):
        import os
        CALLS_ROOT.mkdir(parents=True, exist_ok=True)
        os.startfile(str(CALLS_ROOT))

    def _on_quit(self, icon, item):
        if self.state == STATE_RECORDING:
            self.stop_recording()
        self.icon.stop()

    def toggle_recording(self):
        with self.lock:
            if self.state == STATE_IDLE:
                self._start_recording_locked()
            elif self.state == STATE_RECORDING:
                self._stop_recording_locked()
            # ignore toggle while loading or transcribing

    def stop_recording(self):
        with self.lock:
            if self.state == STATE_RECORDING:
                self._stop_recording_locked()

    def _start_recording_locked(self):
        self.call_start_time = datetime.now(timezone.utc)
        out_dir = CALLS_ROOT / self.call_start_time.strftime("%Y-%m-%d-%H%M%S")
        self.current_out_dir = out_dir
        self.recorder = CallRecorder(out_dir)
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

    def _load_model_in_background(self):
        self.model = transcriber.load_model(MODEL_SIZE)
        with self.lock:
            self._set_state(STATE_IDLE, title="Ascolto (idle)")

    def run(self):
        keyboard.add_hotkey(HOTKEY, self.toggle_recording)
        threading.Thread(target=self._load_model_in_background, daemon=True).start()
        self.icon.run()


if __name__ == "__main__":
    CALLS_ROOT.mkdir(parents=True, exist_ok=True)
    App().run()

"""One-off test helper: simulates pressing the global hotkey twice (start,
wait, stop) to validate app.py's full pipeline without needing a human at
the keyboard. Run while app.py is already running in another process."""

import sys
import time

import keyboard

record_seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 8

print("Simulating hotkey press (start recording)...")
keyboard.send("ctrl+shift+r")
time.sleep(record_seconds)
print("Simulating hotkey press (stop recording)...")
keyboard.send("ctrl+shift+r")
print("Done sending hotkey events.")

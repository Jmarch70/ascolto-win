"""One-off test helper: exercises start -> pause -> resume -> stop via the
global hotkeys, to validate the pause/resume feature without a human at
the keyboard. Run while app.py is already running in another process."""

import time

import keyboard

print("start recording...")
keyboard.send("ctrl+shift+r")
time.sleep(3)

print("pause...")
keyboard.send("ctrl+shift+p")
time.sleep(2)

print("resume...")
keyboard.send("ctrl+shift+p")
time.sleep(3)

print("stop recording...")
keyboard.send("ctrl+shift+r")
print("done")

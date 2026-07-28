"""One-off smoke test: plays beeps through system audio while capture.py records,
to confirm WASAPI loopback actually captures audio when something is playing."""

import threading
import time
import winsound

import capture


def beep():
    time.sleep(1)
    for _ in range(4):
        winsound.Beep(600, 700)
        time.sleep(0.3)


if __name__ == "__main__":
    threading.Thread(target=beep, daemon=True).start()
    capture.main()

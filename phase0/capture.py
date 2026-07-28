"""
Phase 0 feasibility test: record mic + system audio (WASAPI loopback) simultaneously.

Usage:
    venv\\Scripts\\python.exe capture.py [duration_seconds]

Writes two WAV files into ./captures/<timestamp>/:
    mic.wav      - your microphone
    system.wav   - system audio output (what you hear: the other person's voice, etc.)
"""

import sys
import time
import wave
from datetime import datetime
from pathlib import Path

import pyaudiowpatch as pyaudio

CHUNK = 512
DEFAULT_DURATION = 20


def open_loopback_writer(p, out_path: Path):
    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

    if not default_speakers["isLoopbackDevice"]:
        for loopback in p.get_loopback_device_info_generator():
            if default_speakers["name"] in loopback["name"]:
                default_speakers = loopback
                break
        else:
            raise RuntimeError("Could not find a loopback device matching the default output device.")

    print(f"[system audio] recording from: ({default_speakers['index']}) {default_speakers['name']}")
    print(f"[system audio] channels={default_speakers['maxInputChannels']} rate={int(default_speakers['defaultSampleRate'])}")

    wf = wave.open(str(out_path), "wb")
    wf.setnchannels(default_speakers["maxInputChannels"])
    wf.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
    wf.setframerate(int(default_speakers["defaultSampleRate"]))

    def callback(in_data, frame_count, time_info, status):
        wf.writeframes(in_data)
        return (in_data, pyaudio.paContinue)

    stream = p.open(
        format=pyaudio.paInt16,
        channels=default_speakers["maxInputChannels"],
        rate=int(default_speakers["defaultSampleRate"]),
        frames_per_buffer=CHUNK,
        input=True,
        input_device_index=default_speakers["index"],
        stream_callback=callback,
    )
    return stream, wf


def open_mic_writer(p, out_path: Path):
    default_mic = p.get_device_info_by_index(p.get_default_input_device_info()["index"])

    print(f"[mic] recording from: ({default_mic['index']}) {default_mic['name']}")
    print(f"[mic] channels={default_mic['maxInputChannels']} rate={int(default_mic['defaultSampleRate'])}")

    channels = min(int(default_mic["maxInputChannels"]), 2) or 1
    rate = int(default_mic["defaultSampleRate"])

    wf = wave.open(str(out_path), "wb")
    wf.setnchannels(channels)
    wf.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
    wf.setframerate(rate)

    def callback(in_data, frame_count, time_info, status):
        wf.writeframes(in_data)
        return (in_data, pyaudio.paContinue)

    stream = p.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=rate,
        frames_per_buffer=CHUNK,
        input=True,
        input_device_index=default_mic["index"],
        stream_callback=callback,
    )
    return stream, wf


def main():
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DURATION

    out_dir = Path(__file__).parent / "captures" / datetime.now().strftime("%Y-%m-%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    mic_path = out_dir / "mic.wav"
    system_path = out_dir / "system.wav"

    with pyaudio.PyAudio() as p:
        mic_stream, mic_wf = open_mic_writer(p, mic_path)
        sys_stream, sys_wf = open_loopback_writer(p, system_path)

        print(f"\nRecording for {duration:.0f} seconds. Talk into your mic and/or play some system audio now...")
        for remaining in range(int(duration), 0, -1):
            print(f"  {remaining}s remaining...", end="\r")
            time.sleep(1)
        print("\nStopping.")

        mic_stream.stop_stream()
        sys_stream.stop_stream()
        mic_stream.close()
        sys_stream.close()
        mic_wf.close()
        sys_wf.close()

    print(f"\nSaved:\n  {mic_path}\n  {system_path}")
    return str(out_dir)


if __name__ == "__main__":
    main()

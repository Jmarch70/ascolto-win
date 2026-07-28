"""
Dual-stream WASAPI audio capture: microphone + system audio (loopback),
started and stopped (and paused/resumed) on demand rather than for a fixed
duration.

Adapted from phase0/capture.py, which validated this approach against real
speech and confirmed loopback only produces data while audio is actively
playing (silence -> zero packets, not silent packets -- not a bug).
"""

import wave
from pathlib import Path

import pyaudiowpatch as pyaudio

CHUNK = 512


def list_mic_devices():
    """Returns [(index, name), ...] for real (non-loopback) input devices."""
    devices = []
    with pyaudio.PyAudio() as p:
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0 and not info.get("isLoopbackDevice", False):
                devices.append((i, info["name"]))
    return devices


def list_system_audio_devices():
    """Returns [(index, name), ...] for WASAPI loopback (system audio) devices."""
    devices = []
    with pyaudio.PyAudio() as p:
        for loopback in p.get_loopback_device_info_generator():
            devices.append((loopback["index"], loopback["name"]))
    return devices


class CallRecorder:
    """Records mic.wav and system.wav into out_dir for the duration between
    start() and stop(). pause()/resume() can be called any number of times
    in between -- audio simply isn't written while paused, so the resulting
    files contain no dead air for paused stretches."""

    def __init__(self, out_dir: Path, mic_device_index: int = None, system_device_index: int = None):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.mic_path = self.out_dir / "mic.wav"
        self.system_path = self.out_dir / "system.wav"

        self.mic_device_index = mic_device_index
        self.system_device_index = system_device_index

        self._pa = None
        self._mic_stream = None
        self._sys_stream = None
        self._mic_wf = None
        self._sys_wf = None

        self.mic_device_name = None
        self.system_device_name = None
        self.is_paused = False

    def _open_mic_writer(self):
        if self.mic_device_index is not None:
            device = self._pa.get_device_info_by_index(self.mic_device_index)
        else:
            device = self._pa.get_device_info_by_index(
                self._pa.get_default_input_device_info()["index"]
            )
        self.mic_device_name = device["name"]
        channels = min(int(device["maxInputChannels"]), 2) or 1
        rate = int(device["defaultSampleRate"])

        wf = wave.open(str(self.mic_path), "wb")
        wf.setnchannels(channels)
        wf.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(rate)

        def callback(in_data, frame_count, time_info, status):
            wf.writeframes(in_data)
            return (in_data, pyaudio.paContinue)

        stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            frames_per_buffer=CHUNK,
            input=True,
            input_device_index=device["index"],
            stream_callback=callback,
        )
        return stream, wf

    def _open_loopback_writer(self):
        if self.system_device_index is not None:
            device = self._pa.get_device_info_by_index(self.system_device_index)
        else:
            wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            device = self._pa.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

            if not device["isLoopbackDevice"]:
                for loopback in self._pa.get_loopback_device_info_generator():
                    if device["name"] in loopback["name"]:
                        device = loopback
                        break
                else:
                    raise RuntimeError("Could not find a loopback device matching the default output device.")

        self.system_device_name = device["name"]

        wf = wave.open(str(self.system_path), "wb")
        wf.setnchannels(device["maxInputChannels"])
        wf.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(int(device["defaultSampleRate"]))

        def callback(in_data, frame_count, time_info, status):
            wf.writeframes(in_data)
            return (in_data, pyaudio.paContinue)

        stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=device["maxInputChannels"],
            rate=int(device["defaultSampleRate"]),
            frames_per_buffer=CHUNK,
            input=True,
            input_device_index=device["index"],
            stream_callback=callback,
        )
        return stream, wf

    def start(self):
        self._pa = pyaudio.PyAudio()
        self._mic_stream, self._mic_wf = self._open_mic_writer()
        self._sys_stream, self._sys_wf = self._open_loopback_writer()

    def pause(self):
        for stream in (self._mic_stream, self._sys_stream):
            if stream is not None and stream.is_active():
                stream.stop_stream()
        self.is_paused = True

    def resume(self):
        for stream in (self._mic_stream, self._sys_stream):
            if stream is not None and not stream.is_active():
                stream.start_stream()
        self.is_paused = False

    def stop(self):
        for stream in (self._mic_stream, self._sys_stream):
            if stream is not None:
                if stream.is_active():
                    stream.stop_stream()
                stream.close()
        for wf in (self._mic_wf, self._sys_wf):
            if wf is not None:
                wf.close()
        if self._pa is not None:
            self._pa.terminate()

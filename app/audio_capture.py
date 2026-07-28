"""
Dual-stream WASAPI audio capture: microphone + system audio (loopback),
started and stopped on demand rather than for a fixed duration.

Adapted from phase0/capture.py, which validated this approach against real
speech and confirmed loopback only produces data while audio is actively
playing (silence -> zero packets, not silent packets -- not a bug).
"""

import wave
from pathlib import Path

import pyaudiowpatch as pyaudio

CHUNK = 512


class CallRecorder:
    """Records mic.wav and system.wav into out_dir for the duration between
    start() and stop()."""

    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.mic_path = self.out_dir / "mic.wav"
        self.system_path = self.out_dir / "system.wav"

        self._pa = None
        self._mic_stream = None
        self._sys_stream = None
        self._mic_wf = None
        self._sys_wf = None

        self.mic_device_name = None
        self.system_device_name = None

    def _open_mic_writer(self):
        default_mic = self._pa.get_device_info_by_index(
            self._pa.get_default_input_device_info()["index"]
        )
        self.mic_device_name = default_mic["name"]
        channels = min(int(default_mic["maxInputChannels"]), 2) or 1
        rate = int(default_mic["defaultSampleRate"])

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
            input_device_index=default_mic["index"],
            stream_callback=callback,
        )
        return stream, wf

    def _open_loopback_writer(self):
        wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_speakers = self._pa.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

        if not default_speakers["isLoopbackDevice"]:
            for loopback in self._pa.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    default_speakers = loopback
                    break
            else:
                raise RuntimeError("Could not find a loopback device matching the default output device.")

        self.system_device_name = default_speakers["name"]

        wf = wave.open(str(self.system_path), "wb")
        wf.setnchannels(default_speakers["maxInputChannels"])
        wf.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(int(default_speakers["defaultSampleRate"]))

        def callback(in_data, frame_count, time_info, status):
            wf.writeframes(in_data)
            return (in_data, pyaudio.paContinue)

        stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=default_speakers["maxInputChannels"],
            rate=int(default_speakers["defaultSampleRate"]),
            frames_per_buffer=CHUNK,
            input=True,
            input_device_index=default_speakers["index"],
            stream_callback=callback,
        )
        return stream, wf

    def start(self):
        self._pa = pyaudio.PyAudio()
        self._mic_stream, self._mic_wf = self._open_mic_writer()
        self._sys_stream, self._sys_wf = self._open_loopback_writer()

    def stop(self):
        for stream in (self._mic_stream, self._sys_stream):
            if stream is not None:
                stream.stop_stream()
                stream.close()
        for wf in (self._mic_wf, self._sys_wf):
            if wf is not None:
                wf.close()
        if self._pa is not None:
            self._pa.terminate()

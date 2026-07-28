"""
Phase 0 feasibility test: transcribe mic.wav + system.wav locally on the GPU
using faster-whisper, then merge into one chronological, source-tagged transcript.

Usage:
    venv\\Scripts\\python.exe transcribe.py [captures_dir] [model_size]

    captures_dir defaults to the most recent folder under ./captures
    model_size defaults to "medium" (fits comfortably in 10GB VRAM; try "large-v3" once this works)
"""

import os
import sys
import time
from pathlib import Path

# faster-whisper's GPU backend needs cuBLAS/cuDNN DLLs. Rather than requiring a
# system-wide CUDA Toolkit install, we use the pip-packaged copies (nvidia-cublas-cu12,
# nvidia-cudnn-cu12). CTranslate2's native code loads these via plain LoadLibrary,
# which only honors %PATH% (os.add_dll_directory alone isn't enough), so prepend
# their bin folders to PATH before anything imports ctranslate2/faster_whisper.
_venv_site_packages = Path(__file__).parent / "venv" / "Lib" / "site-packages"
for _pkg in ("cublas", "cudnn"):
    _bin_dir = _venv_site_packages / "nvidia" / _pkg / "bin"
    if _bin_dir.exists():
        os.add_dll_directory(str(_bin_dir))
        os.environ["PATH"] = str(_bin_dir) + os.pathsep + os.environ.get("PATH", "")

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from faster_whisper import WhisperModel

TARGET_SR = 16000


def load_mono_16k(path: Path) -> np.ndarray:
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)  # downmix to mono
    if sr != TARGET_SR:
        from math import gcd
        g = gcd(sr, TARGET_SR)
        mono = resample_poly(mono, TARGET_SR // g, sr // g)
    return mono.astype(np.float32)


def transcribe_source(model, audio: np.ndarray, tag: str):
    t0 = time.time()
    segments, info = model.transcribe(audio, language="en", vad_filter=True)
    segments = list(segments)  # force generator to run now so we can time it
    elapsed = time.time() - t0
    audio_duration = len(audio) / TARGET_SR
    rtf = elapsed / audio_duration if audio_duration > 0 else float("nan")
    print(f"[{tag}] {len(segments)} segment(s), audio={audio_duration:.1f}s, "
          f"transcribe_time={elapsed:.1f}s, real-time-factor={rtf:.2f}x")
    return [(seg.start, seg.end, tag, seg.text.strip()) for seg in segments if seg.text.strip()]


def find_latest_captures_dir() -> Path:
    base = Path(__file__).parent / "captures"
    subdirs = sorted([d for d in base.iterdir() if d.is_dir()])
    if not subdirs:
        raise RuntimeError("No captures found. Run capture.py first.")
    return subdirs[-1]


def main():
    captures_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else find_latest_captures_dir()
    model_size = sys.argv[2] if len(sys.argv) > 2 else "medium"

    mic_path = captures_dir / "mic.wav"
    system_path = captures_dir / "system.wav"

    print(f"Using captures from: {captures_dir}")
    print(f"Loading faster-whisper model '{model_size}' on CUDA...")
    t0 = time.time()
    model = WhisperModel(model_size, device="cuda", compute_type="float16")
    print(f"Model loaded in {time.time() - t0:.1f}s\n")

    all_segments = []

    if mic_path.exists():
        mic_audio = load_mono_16k(mic_path)
        all_segments += transcribe_source(model, mic_audio, "Me")
    else:
        print(f"[mic] no file found at {mic_path}, skipping")

    if system_path.exists():
        sys_audio = load_mono_16k(system_path)
        all_segments += transcribe_source(model, sys_audio, "Them")
    else:
        print(f"[system] no file found at {system_path}, skipping")

    all_segments.sort(key=lambda s: s[0])

    print("\n--- Merged transcript ---\n")
    lines = []
    for start, end, tag, text in all_segments:
        line = f"[{start:6.1f}s] {tag}: {text}"
        print(line)
        lines.append(line)

    out_path = captures_dir / "transcript.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSaved merged transcript to: {out_path}")


if __name__ == "__main__":
    main()

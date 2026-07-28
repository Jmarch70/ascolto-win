"""
Local GPU transcription + call.md writer.

Adapted from phase0/transcribe.py, which validated accuracy and speed
(~10-17x real-time on an RTX 3080) against real speech. The model is loaded
once at app startup (see load_model()) so that stopping a call doesn't pay
the model-load cost every time.
"""

import os
import time
from pathlib import Path

# faster-whisper's GPU backend needs cuBLAS/cuDNN DLLs. This machine has only
# the NVIDIA graphics driver, not the full CUDA Toolkit, so we point at the
# pip-packaged copies instead (nvidia-cublas-cu12, nvidia-cudnn-cu12).
# os.add_dll_directory alone isn't enough -- CTranslate2's native code loads
# these via plain LoadLibrary, which only honors %PATH% -- confirmed in Phase 0.
_venv_site_packages = Path(__file__).parent / "venv" / "Lib" / "site-packages"
for _pkg in ("cublas", "cudnn"):
    _bin_dir = _venv_site_packages / "nvidia" / _pkg / "bin"
    if _bin_dir.exists():
        os.add_dll_directory(str(_bin_dir))
        os.environ["PATH"] = str(_bin_dir) + os.pathsep + os.environ.get("PATH", "")

import numpy as np
import soundfile as sf
import yaml
from scipy.signal import resample_poly
from faster_whisper import WhisperModel

from journal import append_event

TARGET_SR = 16000


def load_model(model_size: str = "medium"):
    # large models are borderline on 10GB VRAM at float16; use a quantized
    # compute type for those to stay safely within budget.
    compute_type = "int8_float16" if model_size.startswith("large") else "float16"
    return WhisperModel(model_size, device="cuda", compute_type=compute_type)


def _load_mono_16k(path: Path) -> np.ndarray:
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    if sr != TARGET_SR:
        from math import gcd
        g = gcd(sr, TARGET_SR)
        mono = resample_poly(mono, TARGET_SR // g, sr // g)
    return mono.astype(np.float32)


def _transcribe_source(model, audio: np.ndarray, tag: str):
    segments, _info = model.transcribe(audio, language="en", vad_filter=True)
    return [(seg.start, seg.end, tag, seg.text.strip()) for seg in segments if seg.text.strip()]


def transcribe_call(model, audio_dir: Path, vault_dir: Path, meta: dict):
    """meta must include: start_time (iso str), end_time (iso str),
    duration_seconds (float), mic_device (str), system_device (str).

    audio_dir holds mic.wav/system.wav/journal.jsonl (stays local, e.g. on D:).
    vault_dir is where call.md gets written (inside the Obsidian vault),
    with a frontmatter link back to audio_dir for re-transcription/listening."""

    append_event(audio_dir, "transcription_started")
    t0 = time.time()

    mic_path = audio_dir / "mic.wav"
    system_path = audio_dir / "system.wav"

    all_segments = []
    if mic_path.exists():
        all_segments += _transcribe_source(model, _load_mono_16k(mic_path), "Me")
    if system_path.exists():
        all_segments += _transcribe_source(model, _load_mono_16k(system_path), "Them")

    all_segments.sort(key=lambda s: s[0])

    transcript_lines = [
        f"[{start:6.1f}s] {tag}: {text}" for start, end, tag, text in all_segments
    ]

    frontmatter = {
        "start_time": meta["start_time"],
        "end_time": meta["end_time"],
        "duration_seconds": round(meta["duration_seconds"], 1),
        "mic_device": meta["mic_device"],
        "system_device": meta["system_device"],
        "audio_folder": str(audio_dir),
    }

    call_md = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n\n" + "\n".join(transcript_lines) + "\n"

    vault_dir.mkdir(parents=True, exist_ok=True)
    call_md_path = vault_dir / "call.md"
    call_md_path.write_text(call_md, encoding="utf-8")

    elapsed = time.time() - t0
    append_event(audio_dir, "transcription_completed", elapsed_seconds=round(elapsed, 1), segment_count=len(all_segments))

    return call_md_path

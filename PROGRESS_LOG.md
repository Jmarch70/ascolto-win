# Progress Log: Windows Meeting Recorder (Ascolto-inspired)

Companion to [PROJECT_BRIEF.md](PROJECT_BRIEF.md) — that file is the forward-looking plan/scope; this file is the append-only record of what's actually happened, so a new session can pick this up cold.

## 2026-07-28 — Origin & scoping

- Started from a question about `github.com/robiyuen-24601/ascolto` (a friend's macOS-only Swift meeting recorder). Confirmed it's Mac-only (SwiftUI, CoreML/Apple Neural Engine, Core Audio) — nothing ports to Windows; would be a full rewrite of UI, audio capture, and transcription layers.
- Evaluated existing local-first alternatives before deciding to build custom:
  - **Screenpipe** (`mediar-ai/screenpipe`) — real, Windows-supported, local Whisper transcription, but it's an always-on "record everything" tool (screen + audio), not meeting-specific.
  - **Hyprnote / anarlog** (`fastrepl/hyprnote`, now branded anarlog) — closer in spirit to Ascolto (meeting-specific, local-first, no-bot capture), but confirmed **macOS-only (Apple Silicon)** as of this session — no Windows build exists despite earlier "coming soon" signals.
- Decision: build a custom, minimal Windows equivalent rather than adopt either.

## Decisions locked in (see PROJECT_BRIEF.md §2 for full rationale)

- **GPU**: confirmed NVIDIA GeForce RTX 3080, 10GB VRAM, driver 610.47 — CUDA path is available.
- **Trigger**: manual only (tray icon click + hotkey). No auto-detection of meeting apps. User doesn't have frequent meetings right now (between jobs) and would rather trigger manually than run an always-on background detector. This also removes what would have been the least reliable part of the design.
- **UI**: tray icon only, no overlay/library window — Claude Code handles analysis downstream, so a full custom UI clone isn't worth building.
- **Speaker labels**: no true diarization needed — dual-stream capture (mic vs system audio) gives "Me"/"Them" tagging essentially for free at the segment level.
- **Project location**: `D:\claude-projects\ascolto-win`, separate from the Obsidian notes vault (Vault01).
- **Model choice for this session's work**: stayed on Sonnet 5 high rather than switching to Opus — this class of task (calling well-documented libraries: NAudio/pyaudiowpatch, faster-whisper) doesn't need Opus-level reasoning, and the user is on a Pro plan where usage quota is a real constraint worth conserving.

## Phase 0 — Feasibility spike: COMPLETE, both hard unknowns confirmed

Location: `phase0/` (Python venv + two scripts: `capture.py`, `transcribe.py`)

**What was tested:**
1. Simultaneous WASAPI dual-stream capture (mic + system-audio loopback) via `pyaudiowpatch`
2. Local GPU-accelerated transcription via `faster-whisper` (CTranslate2 backend) on the RTX 3080

**Results:**
- Dual-stream capture works cleanly. Confirmed devices: mic = "Microphone (C922 Pro Stream Web[cam])" at 44.1kHz; system loopback = "Speakers (Realtek(R) Audio)" at 48-192kHz (varies by session).
- **Gotcha discovered**: WASAPI loopback only produces audio packets while something is actively rendering audio — silence produces zero frames, not silent frames. Not a bug; confirmed by testing with `winsound.Beep` playing during capture.
- Transcription quality on real speech: accurate, coherent, correct sentence breaks, no hallucination.
- Transcription speed on RTX 3080 (model: `medium`, compute_type: `float16`): **real-time factor ~0.06–0.10x**, i.e. roughly 10–17x faster than real-time. A full hour-long call would transcribe in a few minutes.
- Mic/system separation gives natural "Me"/"Them" tagging per transcript segment without any diarization model.

**Gotcha requiring a real fix (solved, carries into Phase 1):**
- `faster-whisper`'s GPU path failed with `RuntimeError: Library cublas64_12.dll is not found or cannot be loaded`. Root cause: this machine has the NVIDIA graphics driver but not the full CUDA Toolkit, so cuBLAS/cuDNN runtime DLLs aren't present system-wide.
- Fix used: installed the pip-packaged versions (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`, which bundle the DLLs under `site-packages/nvidia/*/bin`) instead of requiring a multi-GB NVIDIA Toolkit install.
- **Important detail**: `os.add_dll_directory()` alone was NOT sufficient — CTranslate2's native code loads these libraries via plain `LoadLibrary` (not `LoadLibraryEx` with search-path flags), which only honors `%PATH%`. The working fix prepends the DLL bin folders to `os.environ["PATH"]` at runtime before importing `faster_whisper`. **The Phase 1 C#/.NET app will hit the same underlying issue** (missing cuBLAS/cuDNN at the OS level) and will need an equivalent fix — either bundling the same DLLs alongside the app, or documenting a one-time setup step for the user.

## Current state / what's next

Phase 0 fully validates the concept. Not yet started: Phase 1 (the real C#/.NET tray-icon app — see PROJECT_BRIEF.md §7 for the phased plan). Paused here at the user's request to consolidate documentation before continuing.

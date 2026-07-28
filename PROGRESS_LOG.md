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

## 2026-07-28 — Phase 1: COMPLETE (built in Python, not C#/.NET)

**Stack change from the original brief**: at build time, this machine had no .NET SDK installed. Rather than requiring a ~1-2GB SDK install and re-solving the CUDA DLL problem in a different library (Whisper.net/whisper.cpp instead of the already-proven faster-whisper), the user chose to build entirely in Python, reusing Phase 0's exact capture/transcription code. Given the trigger is manual-only (not an always-on service), C#/.NET's main advantage — reliability as a background service — mattered less, making this the pragmatic choice.

**What was built**, in `app/` (own venv, same dependency set as `phase0/` plus `pystray`, `Pillow`, `keyboard`, `PyYAML`):
- `audio_capture.py` — `CallRecorder` class, same dual WASAPI mic+loopback approach as Phase 0 but start()/stop() on demand instead of a fixed duration.
- `journal.py` — append-only JSONL event logger (`recording_started`, `recording_stopped`, `transcription_started`, `transcription_completed`, `error`).
- `transcriber.py` — loads the faster-whisper model once at app startup (not per-call, to avoid repeating the ~2-30s load cost), transcribes mic+system after a call ends, writes `call.md` with YAML frontmatter (start/end time, duration, device names) + the merged Me/Them transcript.
- `app.py` — the tray icon app itself: pystray icon with idle/recording/transcribing states (green/red/blue), right-click menu (Start/Stop, Open Calls Folder, Quit), and a global `Ctrl+Shift+R` hotkey via the `keyboard` library. Output goes to `~\Claude\calls\<timestamp>\`, matching the format Ascolto itself uses.

**Testing performed:**
1. Automated smoke test: simulated the hotkey twice from a second script (`simulate_hotkey_test.py`) while the app ran in the background — validated the full pipeline (start → capture → stop → transcribe → write files) with zero human interaction. Correctly produced 0 transcript segments on an 8-second silent clip (VAD filtering working as expected).
2. Real end-to-end test by the user: pressed the hotkey, talked for ~29 seconds with a video playing through headphones, pressed again to stop. Result: 11 segments, correctly tagged Me/Them, transcribed in 4.2s (real-time factor ~0.15x). Confirmed accurate, coherent transcription and correct file output (`call.md`, `journal.jsonl`, `mic.wav`, `system.wav`).

**Known rough edges / not yet done:**
- No installer/packaging — currently run manually via `venv\Scripts\python.exe app.py`. Not set to start automatically at login (intentionally, since manual-trigger was the whole point).
- No settings UI (device selection, model size, calls folder location are all hardcoded constants at the top of `app.py`).
- No pause/resume mid-call.
- The `keyboard` library's global hotkey hook has known quirks in some contexts (e.g. elevated/admin windows can block it) — not yet stress-tested against that.

## Current state / what's next

Both Phase 0 and Phase 1 are complete and validated with real usage. The core product works: manual hotkey/tray trigger, dual-channel local capture, fast accurate local GPU transcription, markdown output ready for Claude Code. Remaining work is polish (Phase 2 in the brief: settings, packaging, crash recovery, pause/resume) — not yet started, and not urgent given the app already works for its intended use.

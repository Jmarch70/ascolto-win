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

## 2026-07-28 — Settings + pause/resume: COMPLETE

Added the two remaining items from Phase 1's "rough edges" list:

- **`config.py`** — persists mic device, system-audio device, model size, and calls folder to `~/.ascolto_win/config.json`. `audio_capture.py`'s `CallRecorder` now accepts explicit device index overrides (falls back to system default when `None`), and gained `list_mic_devices()`/`list_system_audio_devices()` helpers.
- **`settings_window.py`** — a tkinter dialog (opened via a dedicated thread, its own `Tk()` instance, separate from pystray's loop) with dropdowns for mic/system device and model size, plus a folder browser for the calls location. Device/folder changes apply to the next recording; changing the model size triggers a background reload (tray icon shows "loading" state again) without needing to restart the whole app.
- **Pause/resume** — `CallRecorder.pause()`/`resume()` just call `stream.stop_stream()`/`start_stream()` on the already-open PyAudio streams, so paused stretches simply aren't written to the WAV files (no dead air, no separate file segments to stitch back together). New `Ctrl+Shift+P` hotkey and tray menu label toggle between "Pause Recording"/"Resume Recording", independent of the `Ctrl+Shift+R` start/stop hotkey. Tray icon adds an orange "paused" state.
- `transcriber.py` now picks `int8_float16` compute type automatically for `large-v3` (float16 would be borderline tight on this machine's 10GB VRAM); `medium` and smaller stay at `float16`.

**Testing:** automated hotkey-simulation scripts (`simulate_pause_test.py`) confirmed the pause/resume audio-exclusion behavior (paused period correctly absent from the output WAV, verified by checking file duration against wall-clock timestamps). The user visually confirmed the Settings window opens/closes correctly and did a real pause/resume recording — journal and transcript both came out correct (clean gap, no dead air, resumed content transcribed properly).

## 2026-07-28 — Split storage: transcripts into the Obsidian vault, audio onto D:

User wanted transcripts to land directly in the Obsidian vault (Vault01) for searchability/linking in Obsidian, while keeping the multi-MB raw audio files off of C: (limited space) and out of the vault's git history (audio bloats a notes-vault repo over time).

**Config schema change**: `calls_root` (single folder) replaced with two independent settings:
- `audio_root` (default `D:\claude-projects\CallAudio\calls`) — mic.wav/system.wav/journal.jsonl
- `vault_root` (default `D:\claude-projects\Vault01\Calls`) — call.md only

`transcriber.transcribe_call()` now takes both `audio_dir` and `vault_dir` separately, writes `call.md` into the vault side, and adds an `audio_folder` frontmatter field pointing back to the audio location for traceability (so a note in Obsidian can always find its source audio for re-transcription or listening). `app.py` and `settings_window.py` updated to match (two folder pickers in Settings now, and two "Open ... Folder" tray menu items instead of one).

**Migration**: one real call from earlier testing (2026-07-28-192328, the "customer reference/value prop" test) was still sitting in the old default location (`~/Claude/calls`) and got manually migrated into the new split structure rather than deleted, since it was real content, not throwaway test data. The old `~/Claude/` folder and the old-schema `config.json` were removed since nothing else referenced them.

**Testing**: automated hotkey-simulated recording confirmed `call.md` lands cleanly in `Vault01/Calls/<timestamp>/` with the audio_folder pointer, and audio+journal land in `CallAudio/calls/<timestamp>/` on D:.

## 2026-07-28 — Pushed to GitHub

Created a new **public** repo, [`Jmarch70/ascolto-win`](https://github.com/Jmarch70/ascolto-win), and pushed all local history to it. Added `README.md` (credits [Rob's original Ascolto](https://github.com/robiyuen-24601/ascolto) up front as the direct inspiration, explains why this is a from-scratch Windows build rather than a port) and `app/requirements.txt` (generated from the actual venv via `pip freeze`) beforehand so the repo is usable by someone landing on it cold. Confirmed via `git ls-files` that only source + docs are tracked — no venvs, no audio, nothing bulky. User was told upfront the docs mention his name and "between jobs" status and chose public anyway.

## Current state / what's next

Phase 0, Phase 1, the settings/pause-resume follow-up, and the vault storage split are all complete and validated. The app now supports: manual hotkey/tray trigger, pause/resume mid-call, configurable devices/model/two storage locations, dual-channel local capture, fast accurate local GPU transcription, and transcripts landing directly in the Obsidian vault. Remaining open items are lower priority: no installer/packaging (still run via `venv\Scripts\python.exe app.py`), not set to auto-start at login, no crash-recovery testing beyond the journal log existing.

**Planned next step (not started)**: measure actual transcription accuracy rather than relying on eyeballing outputs. Plan is to have the user read a known paragraph aloud, then diff the resulting transcript word-for-word against the source text to get a real word-error-rate figure for this specific mic/room/model setup — current accuracy claims are qualitative only (outputs have looked coherent and correct in every real test so far, but nothing's been measured against ground truth).

## 2026-07-28 — Companion `summarize-call` Claude Code skill (lives in the vault, not this repo)

This repo only produces the raw transcript (`call.md`). To turn that into a Granola-style summary (TL;DR, key points, decisions, action items), added a project-scoped skill at `Vault01/.claude/skills/summarize-call/SKILL.md` — outside this repo, since it's a vault-side workflow tool, not app code. It reads a given call's `call.md`, asks before guessing who "Them" is if that matters for the summary, and appends a `## Summary` section above the existing transcript without altering the transcript itself. Auto-available in any Claude Code session rooted in Vault01, no per-session setup.

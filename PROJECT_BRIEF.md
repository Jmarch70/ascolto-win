# Project Brief: Windows Meeting Recorder (Ascolto-inspired)

## 1. Goal

A Windows app, started manually when you want it (tray icon click or a hotkey — not always-on, no auto-detection), that:
1. Records both your microphone and system audio (what you hear) for the duration
2. Transcribes the call **fully locally** — no audio or text leaves the machine
3. Writes the result to disk in a format designed to be read and analyzed by Claude Code afterward

This is a new build inspired by Ascolto's design, not a port — Ascolto's actual code (Swift/SwiftUI/CoreML) is Mac-only and none of it is reusable on Windows, as covered earlier.

## 2. Decisions locked in so far

| Decision | Choice | Why |
|---|---|---|
| GPU | **Confirmed: NVIDIA GeForce RTX 3080** — build for CUDA-accelerated transcription | Checked directly on this machine; no need for a CPU-only fallback as the default path. |
| Trigger | **Manual only** — tray icon click (+ optional hotkey), no auto-detection | You confirmed you don't have frequent meetings right now and would rather trigger it yourself than run an always-on background detector. This also removes the least-reliable part of the original design (see §7, dropped Phase 2). |
| UI | **Tray icon only**, no menu-bar pill/overlay, no library window | You said Claude Code does the analysis — a full custom UI is the most expensive part of Ascolto to clone and adds the least value here. |
| Speaker labels | **No diarization** — single merged, timestamped transcript, audio source tagged (mic vs system) in metadata | Cuts real engineering complexity; Claude Code can usually infer speaker from context, and you can add diarization later without redoing the pipeline. |
| Project location | **Separate folder**, `D:\claude-projects\ascolto-win`, own git repo | Vault01 is your Obsidian notes vault (job search/RevOps) — this is a software project and shouldn't live mixed in with it. |

## 3. Functional requirements (mapped from Ascolto)

| Ascolto feature | Windows equivalent |
|---|---|
| Auto-detects mic access by meeting apps | **Dropped** — you start/stop it yourself via tray icon or hotkey |
| Dual-channel capture (mic + system) | WASAPI: mic capture stream + WASAPI **loopback** capture stream for system output, recorded in parallel |
| Local transcription | `faster-whisper` (CTranslate2-based Whisper) running on the RTX 3080 via CUDA |
| Markdown output, crash-safe | `call.md` (frontmatter + transcript) + `journal.jsonl` (append-only progress log, so a crash mid-call doesn't lose everything) written the same way Ascolto does it |
| Library/search UI | Skipped for v1 — Claude Code + plain file search over the markdown folder covers this |
| Optional AI summary via Claude CLI | Skipped — you're doing this yourself downstream in Claude Code |

## 4. Output format (designed for Claude Code ingestion)

Mirrors Ascolto's structure so it drops into the same kind of workflow you described:

```
~\Claude\calls\2026-07-28-1430\
  call.md          # YAML frontmatter (date, duration, detected app, audio devices) + transcript
  audio.wav         # or .m4a — raw recording, kept so you can re-transcribe later if the model improves
  journal.jsonl      # append-only event log: call started, chunk transcribed, call ended, errors
```

`call.md` frontmatter fields: start time, end time, duration, detected source app (best guess), audio device names. Transcript body is plain markdown with timestamps, no speaker labels (per assumption above).

## 5. Architecture

```
┌─────────────────────┐
│ Tray Icon Trigger     │  you click "Start Recording" (or hit the
│                       │  hotkey) — this is the only entry point
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│ Audio Capture Engine  │  WASAPI mic stream + WASAPI loopback stream,
│                       │  written to disk as the call progresses
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│ Transcription Worker  │  faster-whisper running locally, processes
│                       │  audio in chunks (so partial transcript exists
│                       │  even if the call is still going / app crashes)
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│ Markdown Writer       │  assembles call.md + journal.jsonl per the
│                       │  format above
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│ Tray Icon updates     │  icon reflects idle/recording/transcribing
│                       │  state; right-click for stop/quit/settings
└───────────────────────┘
```

## 6. Tech stack recommendation

**C#/.NET 8 desktop app**, using:
- **NAudio** — mature, well-documented library for WASAPI capture and loopback recording on Windows
- **Whisper.net** (or shelling out to `faster-whisper` as a local subprocess) for transcription
- **WinForms `NotifyIcon`** (or WinUI 3 if we want a more modern tray/settings experience) for the tray icon and minimal settings window
- Packaged as a simple installer (Inno Setup) or just a portable folder to start — no need for an app-store-grade installer for personal use

Why C# over alternatives: NAudio + WASAPI loopback is a solved, well-trodden path on Windows; tray-icon apps are a standard .NET pattern; and it avoids the packaging headaches of shipping a background Python process reliably at every Windows login.

**Alternative considered:** Python (`pyaudiowpatch` for WASAPI loopback + `faster-whisper` directly, no subprocess). Faster to prototype, but clunkier to make into a reliable always-running background app with a tray icon and startup registration. Worth using only for a **throwaway Phase 0 feasibility test**, not the real build.

## 7. Phased plan

**Phase 0 — Feasibility spike (hours, not days)**
Quick script: capture 30 seconds of WASAPI loopback + mic simultaneously, feed to `faster-whisper` on the RTX 3080, confirm transcription quality and speed on your actual hardware. Throwaway code — de-risks the two hardest technical unknowns before committing to the full build.

**Phase 1 — Core recording pipeline**
C#/.NET app: tray icon with "Start/Stop Recording" (+ hotkey) → WASAPI dual-stream capture → write raw audio to disk → batch-transcribe with faster-whisper → write `call.md`/`journal.jsonl`. This is the whole app for v1 — no auto-detection phase needed.

**Phase 2 — Polish**
Tray icon states (idle/recording/transcribing), settings (device picker, storage location), crash recovery, pause/resume mid-call.

**Phase 3 (optional, later)** — speaker diarization if it turns out you want it, or auto-detection if your meeting volume picks up again and manual triggering gets tedious.

## 8. Known risks / open questions

- **Legal/consent**: recording other participants' audio may require notice or consent depending on jurisdiction and company policy — worth a quick check on your end since this will be used in real interviews/meetings.
- **Forgetting to click start**: the main downside of manual-only triggering is simply forgetting to hit the button before a call starts. Not a technical risk, just a habit to build — a hotkey helps since it's faster than finding the tray icon.

## 9. What I need from you to start Phase 0

Nothing further — GPU is confirmed, scope is locked in above. Say the word and I'll build the Phase 0 feasibility script.

# ascolto-win

A local-only, Windows-native meeting recorder: press a hotkey to start recording, it captures both your microphone and system audio (what you hear) at once, transcribes everything locally on-GPU, and writes the result straight into an Obsidian vault as a markdown note.

## Credit where it's due

This project is directly inspired by [**Ascolto**](https://github.com/robiyuen-24601/ascolto), a macOS meeting recorder built by [Rob](https://github.com/robiyuen-24601). Ascolto auto-detects calls, records dual-channel audio, and transcribes locally using Apple's Neural Engine, writing everything out as clean markdown.

Ascolto itself is Swift/SwiftUI/CoreML and Apple Silicon-only, so none of its code carries over to Windows — this is a from-scratch reimplementation of the same idea (local-first, privacy-respecting, markdown-native call recording) built for Windows, not a port. See [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) for the full breakdown of what would and wouldn't have ported.

## What it does

- **Manual trigger** — `Ctrl+Shift+R` or a tray-icon click to start/stop; `Ctrl+Shift+P` to pause/resume mid-call. No always-on background detection.
- **Dual-channel capture** — microphone and system-audio (WASAPI loopback) recorded simultaneously, which gives "Me"/"Them" tagging for free without needing a speaker-diarization model.
- **Fully local transcription** — [faster-whisper](https://github.com/SYSTRAN/faster-whisper) running on your GPU. No audio or text ever leaves the machine.
- **Configurable** — pick your mic/system-audio device, transcription model size, and where files land, via a tray-menu Settings dialog.
- **Markdown-native output** — transcripts land as `call.md` (YAML frontmatter + timestamped, speaker-tagged transcript) ready to drop into an Obsidian vault or feed to an LLM for analysis. Raw audio + a crash-safe event journal are kept in a separate local folder.

## Status

Working end-to-end, including settings and pause/resume. See [`PROGRESS_LOG.md`](PROGRESS_LOG.md) for the full build history, technical gotchas (e.g. the CUDA cuBLAS/cuDNN DLL issue on machines without a full CUDA Toolkit install), and what's still rough (no installer/packaging yet, no auto-start).

## Requirements

- Windows 10/11
- Python 3.11+
- An NVIDIA GPU is strongly recommended (this was built/tested against an RTX 3080); CPU-only transcription will work but is much slower

## Setup

```powershell
cd app
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python.exe app.py
```

First launch also generates `~/.ascolto_win/config.json` with defaults — open Settings from the tray icon to point the mic/system-audio device, transcription model, and storage folders wherever you want.

## License

No license file yet — treat as all-rights-reserved until one is added.

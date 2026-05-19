# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

local-transcribe — a local, offline voice transcription tool for Windows. Two modes:
1. **Push-to-talk** — hold Caps Lock, speak (or capture system audio), release, text types itself anywhere
2. **Meeting mode** — captures system audio (speakers/headphones) and saves rolling transcript to file

Push-to-talk supports two audio sources (configurable via tray menu or `settings.json`):
- **Microphone** (default) — captures mic input
- **System Audio (loopback)** — captures whatever is playing through speakers/headphones via WASAPI loopback (requires `pyaudiowpatch`)

Adapted from https://github.com/mikecann/mikerosoft (voice-type and transcribe tools).

## Tech Stack

- Python 3.11 (Windows)
- faster-whisper — local Whisper transcription (no API)
- sounddevice — mic and system audio capture
- pyaudiowpatch — WASAPI loopback capture for system audio in push-to-talk mode
- scipy — audio resampling (loopback devices use native sample rates)
- pystray + Pillow — system tray icon
- tkinter — overlay UI
- llama-cpp-python is NOT installed; formatter feature is disabled, skip entirely

## Key Files

- `voice-type.py` — main entry point, hotkey loop, overlay, tray, settings UI
- `platform_win.py` — Windows-specific audio, keyboard injection, hotkey
- `meeting_mode.py` — WASAPI loopback capture, rolling transcript writer
- `speech_backends.py` — MLX/faster-whisper model abstraction
- `text_formatter.py` — LLM-based text cleanup (disabled by default, needs llama-cpp-python)
- `preview_format.py` — overlay preview text wrapping
- `runtime_policy.py` — per-platform mic stream policy
- `voice_type_control.py` — Unix-socket control server (macOS only, unused on Windows)
- `settings.json` — persisted user settings (model, language, audio source, corrections, etc.)
- `start.bat` — double-click to launch

## Audio Source Switching

The `Recorder` class in `voice-type.py` supports two backends:
- **Mic**: uses `sounddevice.InputStream` at 16kHz mono (no conversion needed)
- **Loopback**: uses `pyaudiowpatch` to open the default WASAPI output device as a loopback input at its native sample rate/channels, then `_convert_audio()` downmixes to mono and resamples to 16kHz via `scipy.signal.resample_poly`

The stream is reopened automatically when the audio source setting changes (detected in `_ensure_stream()`). `sounddevice` does not enumerate WASAPI loopback devices on most Windows systems, so `pyaudiowpatch` is the primary loopback backend.

## Hotkey

Caps Lock (0x14) — hold to record, release to transcribe and type.

## Translation Mode

A "Task" setting (`transcribe` / `translate`) is exposed in the tray menu and `settings.json`. It passes `task=` to `model.transcribe()`. However:

- **`large-v3-turbo` does NOT reliably translate** — it ignores the `task="translate"` parameter and outputs the original language. This appears to be a model limitation (distilled for transcription only).
- `large-v3` on CPU with int8 is very slow and also produced gibberish in testing.
- **TODO**: find a model/configuration that reliably translates. Options to investigate:
  - `large-v3` on GPU (float16) — may work once GPU is running
  - `large-v2` — older but known to support translation
  - Increase `beam_size` for translate task (greedy decoding may hurt translation)

## Known Issues / TODOs

- **Cancel/stop transcription**: there is currently no way to abort a transcription in progress (e.g. if you accidentally hold Caps Lock too long). Need a mechanism to cancel.
- **GPU not working**: `ctranslate2` detects 1 CUDA device, but faster-whisper may fail to load on GPU if cuBLAS/cuDNN DLLs are missing from PATH. The `cublas64_12.dll` check was removed but GPU loading may still error at runtime. Need to test and fix.
- **Translation not working**: see Translation Mode section above.

## Git Workflow

### Files to NOT push (add to `.gitignore`):
- `__pycache__/` — compiled Python bytecode
- `*.pyc` — compiled Python files
- `voice-type.log` — runtime log (contains local device names, transcription output)
- `voice-type.instance.lock` — runtime lock file
- `voice-type.heartbeat` — runtime heartbeat file
- `settings.json` — contains user-specific device/model preferences (ship a `settings.example.json` instead if needed)
- `*.egg-info/`, `dist/`, `build/` — packaging artifacts
- `.env` — if ever added

### Sensitive information review:
- **No API keys or credentials** in this repo — all processing is local
- `settings.json` — not sensitive per se but user-specific (device names, preferences)
- `voice-type.log` — contains local device names and transcription text; don't push

### How to push:
```bash
# 1. Create .gitignore first (see above)
# 2. Stage source files only
git add voice-type.py platform_win.py meeting_mode.py speech_backends.py \
        text_formatter.py preview_format.py runtime_policy.py voice_type_control.py \
        list_devices.py start.bat icons/ CLAUDE.md DEV_NOTES.md README.md

# 3. Commit
git commit -m "description of changes"

# 4. Push
git remote add origin <your-repo-url>   # first time only
git push -u origin main
```

Or simply create the `.gitignore` and use `git add -A` — the ignored files will be excluded automatically.

## Conventions

- All audio runs locally, no cloud, no API keys
- Keep changes minimal, no over-engineering
- Test each feature before moving to the next

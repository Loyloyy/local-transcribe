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
- sounddevice — microphone capture
- pyaudiowpatch — WASAPI loopback capture for system audio (used in both push-to-talk loopback mode and meeting mode)
- scipy — audio resampling (loopback devices use native sample rates)
- pystray + Pillow — system tray icon
- tkinter — overlay UI
- llama-cpp-python is NOT installed; formatter feature is disabled, skip entirely

## Key Files

- `voice-type.py` — main entry point, hotkey loop, overlay, tray, settings UI, cancellation mechanism
- `platform_win.py` — Windows-specific audio, keyboard injection, hotkey
- `meeting_mode.py` — WASAPI loopback capture, rolling transcript writer (uses pyaudiowpatch)
- `text_formatter.py` — LLM-based text cleanup (disabled by default, needs llama-cpp-python)
- `preview_format.py` — overlay preview text wrapping
- `runtime_policy.py` — per-platform mic stream policy
- `settings.json` — persisted user settings (model, language, audio source, corrections, etc.)
- `start.bat` — double-click to launch

## Audio Source Switching

The `Recorder` class in `voice-type.py` supports two backends:
- **Mic**: uses `sounddevice.InputStream` at 16kHz mono (no conversion needed)
- **Loopback**: uses `pyaudiowpatch` to open the default WASAPI output device as a loopback input at its native sample rate/channels, then `_convert_audio()` downmixes to mono and resamples to 16kHz via `scipy.signal.resample_poly`

The stream is reopened automatically when the audio source setting changes (detected in `_ensure_stream()`). `sounddevice` does not enumerate WASAPI loopback devices on most Windows systems, so `pyaudiowpatch` is the primary loopback backend.

## GPU Support

CUDA GPU acceleration is detected automatically via `platform.cuda_available()`. Both the final model and stream model attempt GPU loading first, with automatic CPU fallback:

1. Try loading the model on CUDA with float16 compute type
2. Run a warm-up inference to verify the GPU actually works (catches missing DLLs)
3. If anything fails, log the error and fall back to CPU with int8 quantization

To enable GPU acceleration, install PyTorch with CUDA support:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu124
```
Match the CUDA toolkit version to your system (cu118, cu121, cu124, etc.).

## Hotkey

Caps Lock (0x14) — hold to record, release to transcribe and type.

## Cancellation Mechanism

In-flight transcriptions can be cancelled by pressing the hotkey again (starting a new recording). The mechanism:
- `_finalize_cancel` (`threading.Event`) tracks the current finalize pass
- On key-down: any existing cancel event is set, aborting the previous transcription
- On key-up: a fresh event is created and passed to the finalize thread
- `transcribe()` checks `cancel_event.is_set()` between segments
- `_transcribe_with_timeout()` wraps transcription in a 60-second timeout

## Translation Mode

A "Task" setting (`transcribe` / `translate`) is exposed in the tray menu and `settings.json`. It passes `task=` to `model.transcribe()`.

- **`large-v3` works** for translation (tested on GPU with float16)
- **`large-v3-turbo` does NOT reliably translate** — it ignores the `task="translate"` parameter and outputs the original language (distilled for transcription only)
- `large-v2` also supports translation
- English-only models (`.en` suffix) cannot translate; the stream model auto-overrides to `lang="en"` + `task="transcribe"` when a `.en` model is used with a non-English language setting

## Known Issues / TODOs

- **Translation model selection**: `large-v3-turbo` doesn't translate. Users must manually switch to `large-v3` or `large-v2` for translation. Consider auto-switching or adding a warning.
- **Stabilized mode + cancellation**: if cancelled mid-injection, partial text may remain in the target window.

## Git Workflow

### Files to NOT push (add to `.gitignore`):
- `__pycache__/` — compiled Python bytecode
- `*.pyc` — compiled Python files
- `voice-type.log` — runtime log (contains local device names, transcription output)
- `voice-type.instance.lock` — runtime lock file
- `voice-type.heartbeat` — runtime heartbeat file
- `settings.json` — contains user-specific device/model preferences
- `meeting_*.txt` — meeting mode transcript files
- `.env` — if ever added

### Sensitive information review:
- **No API keys or credentials** in this repo — all processing is local
- `settings.json` — not sensitive per se but user-specific (device names, preferences)
- `voice-type.log` — contains local device names and transcription text; don't push

### How to push:
```bash
# 1. Create .gitignore first (see above)
# 2. Stage source files only
git add voice-type.py platform_win.py meeting_mode.py \
        text_formatter.py preview_format.py runtime_policy.py \
        list_devices.py start.bat icons/ CLAUDE.md DEV_NOTES.md README.md .gitignore

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

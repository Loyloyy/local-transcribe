# local-transcribe

## Why I built this

- Voice input is going to replace a lot of typing. It's already faster and surprisingly accurate even with small models
- I wanted something I could use while working in Claude Code or Codex to just talk out my thoughts and have them appear as text
- Teams translation is slow and inaccurate, and when meeting files live on a client's end you don't always get access to them. So I built a meeting mode that captures system audio locally and produces its own transcript I can summarize later
- Everything runs locally, no cloud APIs, which also keeps things private

## Features

- **Push-to-talk**: hold Caps Lock, speak, release. Transcribed text types itself into any active window.
- **System audio capture**: switch to loopback mode to transcribe what's playing through your speakers/headphones (meetings, videos, podcasts).
- **Meeting mode**: continuous system audio capture with a rolling transcript saved to file.
- **Translation**: translate speech to English from any supported language.
- **System tray**: right-click the tray icon to change models, language, audio source, and other settings.

## Requirements

- Windows 10/11
- Python 3.11

## Install

```bash
pip install faster-whisper sounddevice numpy Pillow pystray huggingface_hub scipy pyaudiowpatch
```

`pyaudiowpatch` is required for system audio capture (WASAPI loopback). If you only need microphone input, it's optional.

## Usage

```bash
python voice-type.py
```

Or double-click `start.bat`.

A microphone icon appears in the system tray. Hold **Caps Lock** to record, release to transcribe and type.

### Switching audio source

Right-click the tray icon, then **Audio Source**:

- **Microphone** (default): captures your mic
- **System Audio (loopback)**: captures whatever is playing through your speakers/headphones

When set to System Audio, hold Caps Lock while audio is playing (e.g. a YouTube video, a meeting call), release, and the transcribed text appears at your cursor.

The setting persists in `settings.json` across restarts.

### Meeting mode

Right-click the tray icon, then **Start Meeting Mode**. This continuously captures system audio and writes a timestamped transcript to a `meeting_*.txt` file. Push-to-talk is disabled while meeting mode is active.

### Translation

Right-click the tray icon, then **Task**, then **Translate to English**. Speech in any supported language will be translated to English.

Model compatibility:
- **`large-v3`**: works for translation
- **`large-v2`**: works for translation
- **`large-v3-turbo`**: does **not** reliably translate (ignores the translate task; use `large-v3` instead)
- English-only models (`.en` suffix): cannot translate

### Language

Right-click the tray icon, then **Language** to set the source language. Options include English, Mandarin, Malay, Japanese, and Auto-detect.

Setting a specific language improves accuracy. Auto-detect works but may be less reliable for short utterances.

### GPU acceleration

CUDA GPU acceleration is detected automatically. If a compatible GPU and CUDA stack are available, models load on GPU with float16 precision. If GPU fails for any reason, the app falls back to CPU with int8 quantization, no manual intervention needed.

To enable GPU support, install PyTorch with CUDA:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu124
```

Match the CUDA version to your system (cu118, cu121, cu124, etc.). Without PyTorch+CUDA, the app runs on CPU.

### Cancellation

If a transcription is in progress and you press Caps Lock again to start a new recording, the in-flight transcription is automatically cancelled, no stale text will be pasted. A 60-second timeout also catches stuck transcriptions.

### Models

The tray menu lets you switch between Whisper models:

- **Final Model**: used for the actual transcription (accuracy matters)
- **Preview Model**: used for live overlay while recording (speed matters)

## Settings

All settings are stored in `settings.json` next to the script:

| Key | Default | Description |
|-----|---------|-------------|
| `final_model` | `large-v3-turbo` (GPU) / `small.en` (CPU) | Transcription model |
| `stream_model` | `large-v3-turbo` (GPU) / `tiny.en` (CPU) | Live preview model |
| `output_mode` | `final_only` | Output strategy |
| `audio_source` | `mic` | `mic` or `loopback` |
| `language` | `en` | Language code or `null` for auto-detect |
| `task` | `transcribe` | `transcribe` or `translate` (translate outputs English) |
| `corrections` | `{}` | Word/phrase corrections applied after transcription |

## AI agent compatibility

Project instructions follow the [`AGENTS.md`](https://agents.md/) open standard, so the
codebase can be developed from any AI coding tool:

- **OpenAI Codex, Cursor, Copilot, Windsurf** — read `AGENTS.md` natively.
- **Claude Code** — reads `CLAUDE.md`, a thin bridge that imports `AGENTS.md`.
- **Gemini** — reads `GEMINI.md`, which imports `AGENTS.md`.
- **Cursor** — also picks up `.cursor/rules/agents.mdc`.

`AGENTS.md` is the single source of truth; the others are thin pointers, so the rules never drift.

# local-transcribe

Local, offline voice transcription for Windows. No cloud, no API keys — everything runs on your machine.

## Features

- **Push-to-talk** — hold Caps Lock, speak, release. Transcribed text types itself into any active window.
- **System audio capture** — switch to loopback mode to transcribe what's playing through your speakers/headphones (meetings, videos, podcasts).
- **Meeting mode** — continuous system audio capture with a rolling transcript saved to file.
- **System tray** — right-click the tray icon to change models, language, audio source, and other settings.

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

Right-click the tray icon → **Audio Source**:

- **Microphone** (default) — captures your mic
- **System Audio (loopback)** — captures whatever is playing through your speakers/headphones

When set to System Audio, hold Caps Lock while audio is playing (e.g. a YouTube video, a meeting call), release, and the transcribed text appears at your cursor.

The setting persists in `settings.json` across restarts.

### Meeting mode

Right-click the tray icon → **Start Meeting Mode**. This continuously captures system audio and writes a timestamped transcript to a `meeting_*.txt` file. Push-to-talk is disabled while meeting mode is active.

### Models

The tray menu lets you switch between Whisper models:

- **Final Model** — used for the actual transcription (accuracy matters)
- **Preview Model** — used for live overlay while recording (speed matters)

GPU (CUDA) is detected automatically. CPU uses `int8` quantization for speed.

## Settings

All settings are stored in `settings.json` next to the script:

| Key | Default | Description |
|-----|---------|-------------|
| `final_model` | `large-v3-turbo` (GPU) / `small.en` (CPU) | Transcription model |
| `stream_model` | `large-v3-turbo` (GPU) / `tiny.en` (CPU) | Live preview model |
| `output_mode` | `final_only` | Output strategy |
| `audio_source` | `mic` | `mic` or `loopback` |
| `language` | `en` | Language code or `null` for auto-detect |
| `corrections` | `{}` | Word/phrase corrections applied after transcription |

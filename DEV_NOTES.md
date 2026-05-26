# Dev Notes

Bugs encountered and fixes during development.

## Audio source switching (loopback for push-to-talk)

### 1. Mic audio not flattened after refactor

- **Symptom**: Mic push-to-talk stopped producing transcription output after adding loopback support.
- **Cause**: `_convert_audio()` had an early return (`if not self._using_loopback: return`) that skipped `.flatten()`. Mic audio is shape `(N, 1)` — Whisper needs `(N,)`.
- **Fix**: Always run flatten for both mic and loopback paths.

### 2. Stream not reopened on audio source switch

- **Symptom**: Switching to loopback in the tray menu still captured mic audio. Log showed `rms=0.0001` (silence from loopback perspective).
- **Cause**: `_keep_stream_open=True` meant the mic stream stayed alive. `_ensure_stream()` only checked for errors/inactive, not whether the setting changed.
- **Fix**: Track `_opened_source` and compare against current `audio_source` setting in `_ensure_stream()`.

### 3. No WASAPI loopback devices in sounddevice

- **Symptom**: `find_loopback_device()` returned `None`. No devices with "(loopback)" in `sd.query_devices()`.
- **Cause**: The PortAudio build bundled with `sounddevice` does not enumerate WASAPI loopback devices on most Windows systems.
- **Fix**: Use `pyaudiowpatch` as the loopback backend. It opens the default WASAPI output device as a loopback input stream directly.

### 4. recorder.stop() hanging after loopback capture

- **Symptom**: After releasing Caps Lock, no "Stopped:" log line. Overlay stuck on REC. Hotkey loop blocked.
- **Cause**: `scipy.signal.resample` (FFT-based) on 48kHz audio was extremely slow. Also, no error handling in the key-up path — any exception silently killed the hotkey thread.
- **Fix**: Replaced `resample` with `resample_poly` (polyphase filter, much faster for rational ratios like 48000:16000 = 3:1). Added try/except around key-up handling.

## Meeting mode switched to pyaudiowpatch

- **Problem**: `sounddevice` does not enumerate WASAPI loopback devices on most Windows systems, so meeting mode (which requires system audio capture) could not open a loopback stream.
- **Solution**: Meeting mode now uses `pyaudiowpatch` exclusively to open the default WASAPI output device as a loopback input. This is the same backend used for push-to-talk loopback capture. The `_audio_callback` writes frames into a buffer; `_get_audio_chunk()` extracts, downmixes stereo→mono, and resamples to 16 kHz.

## GPU auto-fallback mechanism

- **Problem**: `ctranslate2` detected 1 CUDA device, but `faster-whisper` would crash at load or inference time if cuBLAS/cuDNN DLLs were missing or incompatible.
- **Solution**: Both `_load_faster_whisper_model()` and `_load_stream_model()` now wrap the GPU load + a warm-up inference in a try/except. If GPU fails for any reason, they log the error and fall back to CPU with int8 quantization. This means GPU acceleration is opportunistic — it works when the right PyTorch/CUDA stack is installed, and degrades gracefully otherwise.
- **PyTorch install for GPU**: `pip install torch --index-url https://download.pytorch.org/whl/cu124` (match your CUDA toolkit version).

## Stream model .en language crash fix

- **Problem**: Setting a non-English language (e.g. `zh`) while using a `.en` stream model (e.g. `tiny.en`) caused faster-whisper to crash with an unsupported-language error during streaming preview passes.
- **Solution**: In `StreamingTranscriber._loop()`, if the stream model name ends with `.en` and the configured language is not English, override `lang` to `"en"` and `task` to `"transcribe"` for that pass only. The final model (which may be multilingual) still uses the configured language.

## Cancellation mechanism

- **Problem**: No way to abort an in-flight transcription. If you accidentally hold Caps Lock on long audio, you'd have to wait for the full transcription to finish before you could record again.
- **Solution**: Added `_finalize_cancel` (a `threading.Event`) and `_finalize_lock`. On key-down, any existing cancel event is set, aborting the previous transcription. On key-up, a fresh event is created and passed through `_transcribe_with_timeout()` → `transcribe()`. The cancel event is checked between segments. A 60-second timeout wrapper catches truly stuck transcriptions.

## Removed macOS-only dead code

- **Deleted** `speech_backends.py` (MLX Whisper wrapper — macOS ARM64 only, always returns None on Windows).
- **Deleted** `voice_type_control.py` (Unix socket IPC — macOS only, never instantiated on Windows).
- **Simplified** `get_model()` to call `_load_faster_whisper_model()` directly without the MLX fallback path.

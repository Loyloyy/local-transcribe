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

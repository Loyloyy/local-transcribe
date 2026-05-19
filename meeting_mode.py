"""Meeting mode — captures system audio via WASAPI loopback and writes a rolling transcript."""

from __future__ import annotations

import os
import time
import threading
import datetime

import numpy as np
import sounddevice as sd


SAMPLE_RATE = 16000
CHUNK_SECONDS = 30       # transcribe every N seconds
OVERLAP_SECONDS = 5      # overlap between chunks for context continuity
MIN_CHUNK_SECONDS = 3    # don't transcribe very short trailing chunks


def find_loopback_device() -> int | None:
    """Find a WASAPI loopback device index, or None if unavailable.

    On Windows, sounddevice exposes WASAPI loopback devices with names
    containing '(loopback)' when the WASAPI host API is available.
    """
    try:
        devices = sd.query_devices()
    except Exception:
        return None

    for idx, dev in enumerate(devices):
        name = dev.get("name", "").lower()
        if "(loopback)" in name and dev.get("max_input_channels", 0) > 0:
            return idx

    return None


def loopback_device_name(device_index: int) -> str:
    try:
        info = sd.query_devices(device_index)
        return info.get("name", f"device {device_index}")
    except Exception:
        return f"device {device_index}"


class MeetingRecorder:
    """Captures system audio via loopback and produces a rolling transcript file."""

    def __init__(self, *, get_model, transcribe_fn, log, language_fn, script_dir: str):
        """
        get_model: callable that returns the loaded whisper model
        transcribe_fn: callable(audio, verbose, language) -> str
        log: logging function
        language_fn: callable() -> str|None returning current language setting
        script_dir: directory to write transcript files into
        """
        self._get_model = get_model
        self._transcribe = transcribe_fn
        self._log = log
        self._language_fn = language_fn
        self._script_dir = script_dir

        self._active = False
        self._thread: threading.Thread | None = None
        self._stream: sd.InputStream | None = None
        self._device_index: int | None = None

        self._lock = threading.Lock()
        self._buffer: list[np.ndarray] = []

        self._transcript_path: str | None = None

    @property
    def active(self) -> bool:
        return self._active

    @property
    def transcript_path(self) -> str | None:
        return self._transcript_path

    def start(self) -> str | None:
        """Start meeting mode. Returns the transcript file path, or None on failure."""
        if self._active:
            return self._transcript_path

        device = find_loopback_device()
        if device is None:
            self._log("Meeting mode: no WASAPI loopback device found. "
                      "Enable 'Stereo Mix' in Windows Sound settings or install "
                      "a virtual audio cable.")
            return None

        self._device_index = device
        dev_name = loopback_device_name(device)
        self._log(f"Meeting mode: using loopback device {device} ({dev_name})")

        # Create transcript file
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._transcript_path = os.path.join(self._script_dir, f"meeting_{ts}.txt")
        with open(self._transcript_path, "w", encoding="utf-8") as f:
            f.write(f"Meeting transcript — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Audio device: {dev_name}\n")
            f.write("=" * 60 + "\n\n")

        with self._lock:
            self._buffer = []

        self._active = True

        # Query the device to get its native sample rate
        dev_info = sd.query_devices(device)
        dev_sr = int(dev_info.get("default_samplerate", SAMPLE_RATE))
        channels = min(dev_info.get("max_input_channels", 2), 2)

        self._dev_sr = dev_sr
        self._dev_channels = channels

        try:
            self._stream = sd.InputStream(
                samplerate=dev_sr,
                channels=channels,
                dtype="float32",
                device=device,
                callback=self._audio_callback,
                blocksize=1024,
            )
            self._stream.start()
        except Exception as e:
            self._log(f"Meeting mode: failed to open loopback stream: {e}")
            self._active = False
            self._transcript_path = None
            return None

        self._thread = threading.Thread(target=self._transcription_loop, daemon=True,
                                        name="meeting-transcriber")
        self._thread.start()

        self._log(f"Meeting mode started. Transcript: {self._transcript_path}")
        return self._transcript_path

    def stop(self):
        """Stop meeting mode."""
        if not self._active:
            return
        self._active = False

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                self._log(f"Meeting mode: stream close error: {e}")
            self._stream = None

        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

        self._log("Meeting mode stopped.")

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            self._log(f"Meeting audio status: {status}")
        if self._active:
            with self._lock:
                self._buffer.append(indata.copy())

    def _get_audio_chunk(self, seconds: float) -> np.ndarray | None:
        """Extract up to `seconds` worth of audio from the buffer, consuming older data."""
        target_samples = int(seconds * self._dev_sr)
        overlap_samples = int(OVERLAP_SECONDS * self._dev_sr)

        with self._lock:
            if not self._buffer:
                return None
            all_audio = np.concatenate(self._buffer, axis=0)
            total_samples = len(all_audio)

            if total_samples < int(MIN_CHUNK_SECONDS * self._dev_sr):
                return None

            # Take up to target_samples
            chunk = all_audio[:target_samples]

            # Keep overlap for next chunk
            keep_from = max(0, len(chunk) - overlap_samples)
            remaining = all_audio[keep_from:]
            self._buffer = [remaining] if len(remaining) > 0 else []

        # Convert to mono if stereo
        if chunk.ndim > 1 and chunk.shape[1] > 1:
            chunk = np.mean(chunk, axis=1)
        chunk = chunk.flatten().astype(np.float32)

        # Resample to 16kHz if device sample rate differs
        if self._dev_sr != SAMPLE_RATE:
            import scipy.signal
            num_samples = int(len(chunk) * SAMPLE_RATE / self._dev_sr)
            chunk = scipy.signal.resample(chunk, num_samples).astype(np.float32)

        return chunk

    def _transcription_loop(self):
        """Periodically transcribe buffered audio and append to the transcript file."""
        # Wait for the model to be ready
        try:
            self._get_model()
        except Exception as e:
            self._log(f"Meeting mode: model load failed: {e}")
            self._active = False
            return

        self._log("Meeting mode: model ready, transcription loop starting.")

        while self._active:
            time.sleep(CHUNK_SECONDS)
            if not self._active:
                break

            audio = self._get_audio_chunk(CHUNK_SECONDS)
            if audio is None or len(audio) < int(MIN_CHUNK_SECONDS * SAMPLE_RATE):
                continue

            duration = len(audio) / SAMPLE_RATE
            self._log(f"Meeting mode: transcribing {duration:.1f}s chunk...")

            t0 = time.perf_counter()
            try:
                text = self._transcribe(audio)
            except Exception as e:
                self._log(f"Meeting mode: transcription error: {e}")
                continue
            elapsed = time.perf_counter() - t0

            if not text or not text.strip():
                self._log(f"Meeting mode: empty transcription ({elapsed:.2f}s)")
                continue

            text = text.strip()
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self._log(f"Meeting mode: [{timestamp}] ({elapsed:.2f}s) {text[:80]}...")

            # Append to transcript file
            try:
                with open(self._transcript_path, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] {text}\n\n")
            except Exception as e:
                self._log(f"Meeting mode: failed to write transcript: {e}")

        # Transcribe any remaining audio on stop
        if not self._active:
            audio = self._get_audio_chunk(CHUNK_SECONDS * 2)
            if audio is not None and len(audio) >= int(MIN_CHUNK_SECONDS * SAMPLE_RATE):
                try:
                    text = self._transcribe(audio)
                    if text and text.strip():
                        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                        with open(self._transcript_path, "a", encoding="utf-8") as f:
                            f.write(f"[{timestamp}] {text.strip()}\n\n")
                        self._log(f"Meeting mode: final chunk transcribed.")
                except Exception as e:
                    self._log(f"Meeting mode: final transcription error: {e}")

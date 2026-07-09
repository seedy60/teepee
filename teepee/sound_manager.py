import logging
from pathlib import Path

log = logging.getLogger(__name__)

try:
    from sound_lib.output import Output
    from sound_lib.stream import FileStream

    HAS_SOUND_LIB = True
except ImportError:
    HAS_SOUND_LIB = False
    log.warning("sound_lib not available. Sound notifications disabled.")


class SoundManager:
    def __init__(self, config):
        self.config = config
        self._output = None
        self._active_streams = []

        if HAS_SOUND_LIB:
            try:
                list_index = config.get("output_device_index", -1)
                bass_device = list_index + 1 if list_index >= 0 else -1
                self._output = Output(device=bass_device)
            except Exception as e:
                log.error("Failed to initialize audio output: %s", e)

    def get_output_devices(self):
        if not HAS_SOUND_LIB or not self._output:
            return ["Default"]
        try:
            return self._output.get_device_names()
        except Exception:
            return ["Default"]

    # Cached parallel list mapping UI-list indices to BASS device indices.
    # Position 0 is the "Default" pseudo-entry (BASS device -1).
    _input_bass_indices = None

    def get_input_devices(self):
        """Enumerate input devices, filtering out loopback ("listen to your
        own speakers") entries that BASS_RecordGetDeviceInfo exposes
        alongside real microphones on Windows. Also populates an internal
        UI-index -> BASS-device-id map so the saved selection still resolves
        correctly after filtering."""
        if not HAS_SOUND_LIB:
            self._input_bass_indices = [-1]
            return ["Default"]
        try:
            import ctypes
            import platform as _platform
            from sound_lib.external.pybass import (
                BASS_DEVICE_ENABLED,
                BASS_DEVICEINFO,
                BASS_RecordGetDeviceInfo,
            )

            # BASS_DEVICE_LOOPBACK is documented as bit 8 but isn't always
            # re-exported by pybass; use the numeric value directly.
            LOOPBACK_FLAG = 8

            names = ["Default"]
            bass_indices = [-1]
            info = BASS_DEVICEINFO()
            i = 0
            while BASS_RecordGetDeviceInfo(i, ctypes.byref(info)):
                flags = info.flags
                if (flags & BASS_DEVICE_ENABLED) and not (flags & LOOPBACK_FLAG):
                    raw = info.name
                    if _platform.system() == "Windows":
                        name = raw.decode("mbcs", errors="replace")
                    elif _platform.system() == "Darwin":
                        name = raw.decode("utf-8", errors="replace")
                    else:
                        name = (
                            raw.decode("utf-8", errors="replace")
                            if isinstance(raw, bytes) else raw
                        )
                    name = name.replace("(", "").replace(")", "").strip()
                    names.append(name)
                    bass_indices.append(i)
                i += 1
            self._input_bass_indices = bass_indices
            return names
        except Exception as e:
            log.debug("Failed to enumerate input devices: %s", e)
            self._input_bass_indices = [-1]
            return ["Default"]

    def get_input_bass_device(self, list_index):
        """Translate a UI-list index (as stored in config) to the underlying
        BASS device id, accounting for any loopback entries that were
        filtered out of ``get_input_devices``."""
        if self._input_bass_indices is None:
            # Build the map lazily.
            self.get_input_devices()
        indices = self._input_bass_indices or [-1]
        if list_index is None or list_index < 0:
            return -1
        if 0 <= list_index < len(indices):
            return indices[list_index]
        return -1

    @staticmethod
    def get_video_devices():
        """Enumerate camera devices on a worker thread (COM-safe)."""
        try:
            from ntgcalls import NTgCalls
            import concurrent.futures

            def _enum():
                devs = NTgCalls.get_media_devices()
                return [cam.name for cam in devs.camera]

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(_enum).result(timeout=5)
        except Exception:
            return []

    def set_output_device(self, list_index):
        if not HAS_SOUND_LIB:
            return
        bass_device = list_index + 1 if list_index >= 0 else -1
        try:
            if self._output is not None:
                try:
                    self._output.free()
                except Exception:
                    pass
                self._output = None
            self._output = Output(device=bass_device)
            self.config["output_device_index"] = list_index
        except Exception as e:
            log.error("Failed to set output device: %s", e)
            if self._output is None:
                try:
                    self._output = Output()
                except Exception:
                    pass

    def play_file(self, path, looping=False):
        if not HAS_SOUND_LIB or not self._output:
            return None
        try:
            stream = FileStream(file=str(path))
            if looping:
                try:
                    stream.looping = True
                except Exception as e:
                    log.warning("Failed to set looping on %s: %s", path, e)
            stream.play()
            self._active_streams.append(stream)
            self._cleanup_finished()
            return stream
        except Exception as e:
            log.error("Failed to play %s: %s", path, e)
            return None

    def _play_looping(self, name):
        if not self.config.get("sounds_enabled", True):
            return None
        sounds_dir = self.config.sounds_dir
        for ext in (".wav", ".mp3", ".ogg"):
            path = sounds_dir / f"{name}{ext}"
            if path.exists():
                return self.play_file(path, looping=True)
        log.debug("Sound file not found: %s", name)
        return None

    def play_notification(self, name):
        if not self.config.get("sounds_enabled", True):
            return
        sounds_dir = self.config.sounds_dir
        for ext in (".wav", ".mp3", ".ogg"):
            path = sounds_dir / f"{name}{ext}"
            if path.exists():
                return self.play_file(path)
        log.debug("Sound file not found: %s", name)

    def play_sent(self):
        self.play_notification("sent")

    def play_received(self):
        self.play_notification("received")

    def play_reply_sent(self):
        self.play_notification("reply_sent")

    def play_reply_received(self):
        self.play_notification("reply_received")

    def play_group_received(self):
        self.play_notification("group_received")

    def play_channel_received(self):
        self.play_notification("channel_received")

    def play_voice_start(self):
        """Play the start-of-recording cue and return its duration in
        seconds, so the caller can defer the actual microphone start until
        the cue has finished. Returns 0 if no cue plays."""
        return self._play_cue_with_duration("voice_start")

    def play_voice_stop(self):
        """Play the end-of-recording cue. Safe to fire right after stopping
        the microphone since the recording is already closed."""
        self._play_cue_with_duration("voice_stop")

    def _play_cue_with_duration(self, base_name):
        if not self.config.get("sounds_enabled", True):
            return 0.0
        sounds_dir = self.config.sounds_dir
        for ext in (".wav", ".mp3", ".ogg"):
            path = sounds_dir / f"{base_name}{ext}"
            if path.exists():
                duration = self._media_duration(path)
                self.play_file(path)
                return duration
        log.debug("Sound file not found: %s", base_name)
        return 0.0

    @staticmethod
    def _media_duration(path):
        """Return the duration of a WAV file in seconds, or 0.0 if it can't
        be determined (e.g. for MP3 / OGG without ffprobe)."""
        try:
            if str(path).lower().endswith(".wav"):
                import wave
                with wave.open(str(path), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    if rate:
                        return frames / float(rate)
        except Exception:
            pass
        return 0.0

    def play_call_in(self):
        sounds_dir = self.config.sounds_dir
        for ext in (".wav", ".mp3", ".ogg"):
            path = sounds_dir / f"call_in{ext}"
            if path.exists():
                return self.play_file(path, looping=True)
        log.debug("Sound file not found: call_in")
        return None

    def play_call_out(self):
        sounds_dir = self.config.sounds_dir
        for ext in (".wav", ".mp3", ".ogg"):
            path = sounds_dir / f"call_out{ext}"
            if path.exists():
                return self.play_file(path, looping=True)
        log.debug("Sound file not found: call_out")
        return None

    def play_ringing(self):
        return self.play_notification("ringing")

    def stop_stream(self, stream):
        if stream is not None:
            try:
                stream.looping = False
                stream.stop()
            except Exception:
                pass

    def stop_ringing(self, stream):
        self.stop_stream(stream)

    def _cleanup_finished(self):
        still_active = []
        for stream in self._active_streams:
            try:
                if stream.is_playing:
                    still_active.append(stream)
            except Exception:
                pass
        self._active_streams = still_active

    def play_test_tone(self):
        if not HAS_SOUND_LIB or not self._output:
            return None
        try:
            import array
            import struct
            import tempfile
            import math

            sample_rate = 44100
            duration = 2
            freq = 440.0
            total = sample_rate * duration
            buf = bytearray(total * 2)
            for i in range(total):
                v = 0.5 * math.sin(2.0 * math.pi * freq * i / sample_rate)
                struct.pack_into("<h", buf, i * 2, int(v * 32767))
            path = Path(tempfile.gettempdir()) / "teepee_test_tone.wav"
            import wave
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(bytes(buf))
            return self.play_file(path)
        except Exception as e:
            log.error("Failed to generate test tone: %s", e)
            return None

    def record_test(self):
        if not HAS_SOUND_LIB:
            return None
        try:
            from sound_lib.input import Input
            from sound_lib.recording import WaveRecording

            list_index = self.config.get("input_device_index", -1)
            bass_device = self.get_input_bass_device(list_index)
            try:
                self._test_input = Input(device=bass_device)
            except Exception:
                # Already initialized (e.g. by VoiceManager) — that's fine,
                # BASS_RecordSetDevice will select the right device.
                from sound_lib.external.pybass import BASS_RecordSetDevice
                if bass_device >= 0:
                    BASS_RecordSetDevice(bass_device)
            import tempfile
            self._test_rec_path = str(
                Path(tempfile.gettempdir()) / "teepee_mic_test.wav"
            )
            rec = WaveRecording(
                filename=self._test_rec_path, frequency=44100, channels=1,
            )
            rec.play()
            return rec
        except Exception as e:
            log.error("Failed to start recording: %s", e)
            return None

    def stop_recording_and_play(self, rec):
        if rec is None:
            return None
        try:
            rec.stop()
            path = getattr(self, "_test_rec_path", None)
            if not path:
                log.warning("No test recording path")
                return None
            return self.play_file(path)
        except Exception as e:
            log.error("Failed to play back recording: %s", e)
            return None

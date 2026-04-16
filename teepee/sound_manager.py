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

    def get_input_devices(self):
        if not HAS_SOUND_LIB:
            return ["Default"]
        try:
            from sound_lib.input import Input

            return Input.get_device_names()
        except Exception:
            return ["Default"]

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
        if stream:
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
            bass_device = list_index - 1 if list_index > 0 else -1
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

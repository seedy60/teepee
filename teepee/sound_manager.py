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

    def play_file(self, path):
        if not HAS_SOUND_LIB or not self._output:
            return None
        try:
            stream = FileStream(file=str(path))
            stream.play()
            self._active_streams.append(stream)
            self._cleanup_finished()
            return stream
        except Exception as e:
            log.error("Failed to play %s: %s", path, e)
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

    def play_group_received(self):
        self.play_notification("group_received")

    def play_channel_received(self):
        self.play_notification("channel_received")

    def _cleanup_finished(self):
        still_active = []
        for stream in self._active_streams:
            try:
                if stream.is_playing:
                    still_active.append(stream)
            except Exception:
                pass
        self._active_streams = still_active

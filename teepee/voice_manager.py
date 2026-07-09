import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

try:
    from sound_lib.recording import WaveRecording

    HAS_RECORDING = True
except ImportError:
    HAS_RECORDING = False

try:
    from pydub import AudioSegment

    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False


class VoiceManager:
    def __init__(self, config, sound_manager):
        self.config = config
        self.sound_manager = sound_manager
        self._recording = None
        self._recording_path = None
        self._playback_stream = None
        self._temp_dir = Path(tempfile.mkdtemp(prefix="teepee_voice_"))
        self._init_input_device()

    def _init_input_device(self):
        if not HAS_RECORDING:
            return
        list_index = self.config.get("input_device_index", -1)
        bass_device = self.sound_manager.get_input_bass_device(list_index)
        try:
            from sound_lib.input import Input

            Input(device=bass_device)
        except Exception as e:
            log.error("Failed to initialize input device: %s", e)

    @property
    def is_recording(self):
        return self._recording is not None

    def start_recording(self):
        if not HAS_RECORDING:
            log.error("sound_lib recording not available")
            return None
        self._recording_path = str(self._temp_dir / "voice.wav")
        try:
            self._recording = WaveRecording(filename=self._recording_path)
            self._recording.play()
            return self._recording_path
        except Exception as e:
            log.error("Failed to start recording: %s", e)
            self._recording = None
            return None

    def stop_recording(self):
        """Stop the active recording and return the raw WAV path, or None if
        nothing was recorded. The caller is then responsible for either
        previewing it, converting it for sending (``convert_for_send``), or
        discarding it (``discard_recording``)."""
        # Use an identity check rather than truthiness: ``bool(WaveRecording)``
        # routes through ``Channel.__bool__`` which calls BASS_ChannelGetLength,
        # and BASS raises ``BASS_ERROR_NOTAVAIL`` if you ask the length of a
        # recording channel that hasn't had time to produce data yet.
        if self._recording is None:
            return None
        try:
            self._recording.stop()
        except Exception as e:
            log.error("Error stopping recording: %s", e)
        self._recording = None

        wav_path = self._recording_path
        self._recording_path = None

        if not wav_path or not os.path.exists(wav_path):
            return None
        return wav_path

    def convert_for_send(self, wav_path):
        """Convert a recorded WAV to OGG/Opus for sending as a Telegram voice
        message. Returns the OGG path, or the original WAV path if pydub /
        ffmpeg are unavailable."""
        if not wav_path or not os.path.exists(wav_path):
            return None
        ogg_path = self._convert_to_ogg(wav_path)
        return ogg_path if ogg_path else wav_path

    def discard_recording(self, wav_path):
        """Delete a recorded WAV (and its OGG sibling, if any) without
        sending."""
        if not wav_path:
            return
        for candidate in (wav_path, wav_path.replace(".wav", ".ogg")):
            try:
                if os.path.exists(candidate):
                    os.remove(candidate)
            except OSError:
                pass

    def _convert_to_ogg(self, wav_path):
        if not HAS_PYDUB:
            log.warning("pydub not available, sending WAV instead of OGG")
            return None
        ogg_path = wav_path.replace(".wav", ".ogg")
        try:
            audio = AudioSegment.from_wav(wav_path)
            audio.export(
                ogg_path,
                format="ogg",
                codec="libopus",
                parameters=["-ar", "48000", "-ac", "1"],
            )
            return ogg_path
        except Exception as e:
            log.error("Failed to convert to OGG: %s", e)
            return None

    def play_voice(self, file_path):
        self.stop_playback()
        playable = self._ensure_playable(file_path)
        self._playback_stream = self.sound_manager.play_file(playable)
        return self._playback_stream

    def _ensure_playable(self, file_path):
        """Convert OGG/Opus to WAV if needed, since BASS doesn't support OGG natively."""
        if not file_path.lower().endswith(".ogg"):
            return file_path
        wav_path = file_path.rsplit(".", 1)[0] + ".wav"
        if os.path.exists(wav_path):
            return wav_path
        if not HAS_PYDUB:
            log.warning("pydub not available, cannot convert OGG to WAV for playback")
            return file_path
        try:
            audio = AudioSegment.from_ogg(file_path)
            audio.export(wav_path, format="wav")
            return wav_path
        except Exception as e:
            log.error("Failed to convert %s to WAV: %s", file_path, e)
            return file_path

    def stop_playback(self):
        if self._playback_stream is not None:
            try:
                self._playback_stream.stop()
            except Exception:
                pass
            self._playback_stream = None

    def get_download_path(self, message_id):
        return str(self._temp_dir / f"voice_{message_id}.ogg")

    @property
    def download_dir(self):
        return str(self._temp_dir)

    def cleanup(self):
        import shutil

        try:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        except Exception:
            pass

import json
import os
from pathlib import Path


DEFAULT_CONFIG = {
    "api_id": "",
    "api_hash": "",
    "output_device_index": -1,
    "input_device_index": -1,
    "camera_device_index": -1,
    "sounds_enabled": True,
    "announcements_enabled": False,
    "announcement_backend": "auto",
    "announcement_voice_index": -1,
    "sound_pack": "default",
    "time_format": "24h",
}


class Config:
    def __init__(self):
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", str(Path.home())))
        else:
            base = Path.home() / ".config"
        self._data_dir = base / "Teepee"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._config_path = self._data_dir / "config.json"
        self._data = dict(DEFAULT_CONFIG)
        self.load()

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    @property
    def session_path(self) -> str:
        return str(self._data_dir / "teepee")

    @property
    def sounds_base_dir(self) -> Path:
        return Path(__file__).parent.parent / "sounds"

    @property
    def sounds_dir(self) -> Path:
        pack = self.get("sound_pack", "default")
        pack_dir = self.sounds_base_dir / pack
        if pack_dir.is_dir():
            return pack_dir
        return self.sounds_base_dir / "default"

    def get_sound_packs(self) -> list:
        base = self.sounds_base_dir
        if not base.is_dir():
            return ["default"]
        packs = sorted(
            d.name for d in base.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )
        return packs if packs else ["default"]

    def load(self):
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

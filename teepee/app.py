import logging
import logging.handlers
import os
import sys
from pathlib import Path

import wx

from . import APP_NAME
from .call_manager import CallManager
from .config import Config
from .sound_manager import SoundManager
from .telegram_manager import TelegramManager
from .ui.main_frame import MainFrame
from .ui.theme import apply_theme, is_legacy_windows, set_theme_override
from .updater import cleanup_old_files
from .voice_manager import VoiceManager


def setup_logging():
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        base = Path.home() / ".config"
    data_dir = base / "Teepee"
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "teepee.log"

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    # File handler (5MB rotating logs, 3 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Specific levels
    logging.getLogger("teepee.call_manager").setLevel(logging.DEBUG)

    # Log unhandled exceptions
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception


class TeepeeApp(wx.App):
    def OnInit(self):
        self.SetAppName(APP_NAME)
        cleanup_old_files()

        self.config = Config()
        # On Windows 8.1 and earlier there's no system dark-mode setting to
        # follow, so honour the user's manual choice from settings.
        if is_legacy_windows():
            set_theme_override(self.config.get("force_dark_theme", False))
        self.telegram_manager = TelegramManager(self.config)
        self.sound_manager = SoundManager(self.config)
        self.voice_manager = VoiceManager(self.config, self.sound_manager)
        self.call_manager = CallManager(self.telegram_manager, self.config)
        self.telegram_manager.call_manager = self.call_manager

        self.telegram_manager.start()

        frame = MainFrame(
            None,
            self.config,
            self.telegram_manager,
            self.sound_manager,
            self.voice_manager,
            self.call_manager,
        )
        frame.Show()
        self.SetTopWindow(frame)
        apply_theme(frame)

        wx.CallAfter(frame.start_connection)
        return True

    def OnExit(self):
        return 0


def main():
    setup_logging()
    logging.info("Starting Teepee...")
    # Normally run.py performs the single-instance check before importing this
    # module (so a second launch exits fast). This is a safety net for any
    # entry point that reaches main() directly; it is idempotent, so when
    # run.py already acquired the mutex it simply returns True here.
    from .single_instance import acquire_or_signal

    if not acquire_or_signal():
        sys.exit(0)

    app = TeepeeApp(redirect=False)
    app.MainLoop()
    # MainLoop returned -- force-terminate to avoid DLL-cleanup deadlocks.
    import signal
    try:
        os.kill(os.getpid(), signal.SIGTERM)
    except Exception:
        os._exit(0)

"""Lightweight single-instance guard.

Kept intentionally dependency-free (only ``ctypes`` / ``os`` / ``pathlib``)
and imported *before* the rest of Teepee, so that a second launch can signal
the already-running instance and exit within milliseconds instead of paying
the multi-second cost of importing wx, telethon, ntgcalls, sound_lib and the
whole UI just to discover it should quit.

A running instance watches for the ``.restore`` file (see MainFrame's restore
timer) and brings itself to the foreground when it appears.
"""
import os
import sys
from pathlib import Path

_MUTEX_NAME = "TeepeeAppMutex"
_ERROR_ALREADY_EXISTS = 183

# Held for the lifetime of the owning process so the named mutex stays alive
# and subsequent launches see it.
_mutex_handle = None


def _data_dir():
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        base = Path.home() / ".config"
    d = base / "Teepee"
    d.mkdir(parents=True, exist_ok=True)
    return d


def acquire_or_signal():
    """Return True if this process should keep running, False if it should
    exit because another instance is already running.

    On Windows, when another instance already holds the mutex, drops a
    ``.restore`` signal file for it to pick up and returns False. Otherwise
    creates and retains the mutex and returns True. Idempotent: calling it
    again in the same process short-circuits to True without re-checking.

    On non-Windows platforms there is no single-instance handling; always
    returns True.
    """
    global _mutex_handle
    if sys.platform != "win32":
        return True
    if _mutex_handle is not None:
        # Already acquired earlier in this same process.
        return True

    import ctypes

    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(
        None, False, _MUTEX_NAME
    )
    already_running = (
        ctypes.windll.kernel32.GetLastError() == _ERROR_ALREADY_EXISTS
    )
    if already_running:
        try:
            (_data_dir() / ".restore").touch()
        except Exception:
            pass
        return False
    return True

"""Secure storage for user secrets backed by the operating system keyring.

On Windows this uses the Credential Locker, on macOS the Keychain, and on
Linux the Secret Service (e.g. GNOME Keyring / KWallet). Secrets never touch
config.json.

In frozen (PyInstaller) builds keyring's entry-point backend discovery can
fail, so the platform backend is set explicitly the first time it is used.
"""
import logging
import sys

log = logging.getLogger(__name__)

_SERVICE = "Teepee"
_backend_ready = False


class KeyringUnavailable(Exception):
    """Raised when no usable OS keyring backend is available."""


def _ensure_backend():
    global _backend_ready
    if _backend_ready:
        return
    import keyring

    if getattr(sys, "frozen", False):
        # Entry-point discovery is unreliable when frozen; pin the native
        # backend so the OS credential store is always used.
        try:
            if sys.platform == "win32":
                from keyring.backends import Windows
                keyring.set_keyring(Windows.WinVaultKeyring())
            elif sys.platform == "darwin":
                from keyring.backends import macOS
                keyring.set_keyring(macOS.Keyring())
        except Exception as e:
            log.warning("Could not set explicit keyring backend: %s", e)

    # Guard against the no-op "fail" backend that keyring falls back to when
    # nothing usable is found.
    try:
        from keyring.backends.fail import Keyring as FailKeyring
        if isinstance(keyring.get_keyring(), FailKeyring):
            raise KeyringUnavailable("No OS keyring backend is available")
    except KeyringUnavailable:
        raise
    except Exception:
        pass

    _backend_ready = True


def is_available() -> bool:
    try:
        _ensure_backend()
        return True
    except Exception:
        return False


def get_secret(name: str) -> str:
    """Return the stored secret, or "" if unset or the keyring is unusable."""
    try:
        _ensure_backend()
        import keyring
        return keyring.get_password(_SERVICE, name) or ""
    except Exception as e:
        log.warning("Could not read secret %r from keyring: %s", name, e)
        return ""


def set_secret(name: str, value: str) -> bool:
    """Store (or, for an empty value, delete) a secret. Returns True on success."""
    try:
        _ensure_backend()
        import keyring
        if value:
            keyring.set_password(_SERVICE, name, value)
        else:
            try:
                keyring.delete_password(_SERVICE, name)
            except Exception:
                # Deleting a non-existent entry is fine.
                pass
        return True
    except Exception as e:
        log.error("Could not store secret %r in keyring: %s", name, e)
        return False

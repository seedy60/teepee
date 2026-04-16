import logging
import sys

log = logging.getLogger(__name__)

_output = None


def _get_output():
    global _output
    if _output is not None:
        return _output
    if sys.platform != "win32":
        return None
    try:
        from accessible_output2.outputs.auto import Auto

        _output = Auto()
    except ImportError:
        log.debug("accessible_output2 not available; screen reader announcements disabled")
        _output = False
    except Exception as e:
        log.debug("Failed to initialize accessible_output2: %s", e)
        _output = False
    return _output


def announce(text, interrupt=False):
    """Announce text to screen readers (NVDA, JAWS, Narrator) on Windows."""
    if not text:
        return
    output = _get_output()
    if not output:
        return
    try:
        output.speak(text, interrupt=interrupt)
    except Exception as e:
        log.debug("Screen reader announcement failed: %s", e)

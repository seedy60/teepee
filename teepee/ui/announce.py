"""Screen-reader announcements with a Prism backend on Windows 10+ and an
``accessible_output2`` backend on Windows 8.1 and earlier (where Prism is
not supported).

Both paths expose the same public API:

* ``announce(text, interrupt=False)``
* ``set_announcements_enabled(enabled)``
* ``set_announcement_preferences(auto_best, backend_name, voice_index)``
* ``list_announcement_backends()``
* ``list_announcement_voices(backend_name)``

so the rest of Teepee (settings dialog, main frame) doesn't need to care
which library is actually doing the speaking.
"""
import logging
import sys

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Platform selection
# ----------------------------------------------------------------------

def _use_ao2():
    """Return True when we should use accessible_output2 instead of Prism.

    Prism doesn't work on Windows 8.1 or earlier, so we fall back to
    accessible_output2 on those systems.
    """
    if sys.platform != "win32":
        return False
    try:
        ver = sys.getwindowsversion()
        return ver.major < 10
    except Exception:
        return False


_USE_AO2 = _use_ao2()


# ----------------------------------------------------------------------
# Shared state
# ----------------------------------------------------------------------

_enabled = False
_auto_best = True
_preferred_backend = ""
_preferred_voice = -1

# Cached backend instance and the key that produced it.
_backend = None
_backend_key = None


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def announce(text, interrupt=False):
    """Speak ``text`` through the active screen reader / TTS backend.

    No-ops if announcements are disabled or no backend is available.
    """
    if not _enabled or not text:
        return
    backend = _get_backend()
    if not backend:
        return
    try:
        if _USE_AO2:
            backend.speak(text, interrupt=interrupt)
        else:
            if interrupt and hasattr(backend, "stop"):
                try:
                    backend.stop()
                except Exception:
                    pass
            backend.speak(text)
    except Exception as e:
        log.debug("Announcement failed: %s", e)


def set_announcements_enabled(enabled):
    global _enabled
    _enabled = bool(enabled)


def set_announcement_preferences(auto_best=True, backend_name="", voice_index=-1):
    """Save the user's announcement preferences and invalidate the cached
    backend so the next call to ``announce`` picks them up."""
    global _auto_best, _preferred_backend, _preferred_voice
    global _backend, _backend_key
    _auto_best = bool(auto_best)
    _preferred_backend = (backend_name or "").strip()
    try:
        _preferred_voice = int(voice_index)
    except Exception:
        _preferred_voice = -1
    _backend = None
    _backend_key = None


def list_announcement_backends():
    return _ao2_list_backends() if _USE_AO2 else _prism_list_backends()


def list_announcement_voices(backend_name=""):
    if _USE_AO2:
        return _ao2_list_voices(backend_name)
    return _prism_list_voices(backend_name)


def _get_backend():
    return _ao2_get_backend() if _USE_AO2 else _prism_get_backend()


# ======================================================================
# Prism path (Windows 10+, Linux, macOS)
# ======================================================================

_prism_ctx = None


def _normalize_backend_token(value):
    return "".join(ch for ch in str(value).upper() if ch.isalnum())


def _prism_get_context():
    global _prism_ctx
    if _prism_ctx is not None:
        return _prism_ctx
    try:
        from prism import Context

        _prism_ctx = Context()
    except ImportError:
        log.debug("Prism not available; screen reader announcements disabled")
        _prism_ctx = False
    except Exception as e:
        log.debug("Failed to initialize Prism context: %s", e)
        _prism_ctx = False
    return _prism_ctx


def _prism_create_backend_for_name(ctx, backend_name):
    if not backend_name:
        return ctx.create_best()
    backend_id = _prism_resolve_backend_id(ctx, backend_name)
    return ctx.create(backend_id)


def _prism_resolve_backend_id(ctx, backend_name):
    from prism import BackendId

    name = (backend_name or "").strip()
    if not name:
        raise ValueError("Backend name is empty")
    normalized = _normalize_backend_token(name)

    # Match against runtime registry entries first (covers all available
    # backends by enum id name and display name).
    try:
        for i in range(ctx.backends_count):
            backend_id = ctx.id_of(i)
            if getattr(backend_id, "name", "") == "INVALID":
                continue
            tokens = [
                _normalize_backend_token(getattr(backend_id, "name", "")),
            ]
            try:
                tokens.append(_normalize_backend_token(ctx.name_of(backend_id)))
            except Exception:
                pass
            if normalized in tokens:
                return backend_id
    except Exception:
        pass

    # Try Prism registry lookup first (accepts backend-specific string ids).
    for candidate in (name, name.lower()):
        try:
            backend_id = ctx.id_of(candidate)
            if getattr(backend_id, "name", "") != "INVALID":
                return backend_id
        except Exception:
            pass

    # Try enum member names, e.g. "SAPI" / "ONECORE".
    enum_key = name.upper().replace("-", "_").replace(" ", "_")
    try:
        return BackendId[enum_key]
    except Exception:
        pass

    # Fuzzy enum lookup: treat ONECORE and ONE_CORE as equivalent.
    normalized = _normalize_backend_token(enum_key)
    for member_name, member in BackendId.__members__.items():
        member_norm = _normalize_backend_token(member_name)
        if member_norm == normalized:
            return member

    # Try numeric literal values (decimal or hex), e.g. "0x...".
    try:
        return BackendId(int(name, 0))
    except Exception:
        pass

    raise ValueError(f"Unsupported backend identifier: {backend_name}")


def _prism_apply_voice_preference(backend):
    if _preferred_voice < 0:
        return
    try:
        features = backend.features
        if not getattr(features, "supports_set_voice", False):
            return
        if getattr(features, "supports_refresh_voices", False):
            backend.refresh_voices()
        if not getattr(features, "supports_count_voices", False):
            return
        count = backend.voices_count
        if 0 <= _preferred_voice < count:
            backend.voice = _preferred_voice
    except Exception as e:
        log.debug("Failed to apply voice preference: %s", e)


def _prism_get_backend():
    global _backend, _backend_key
    key = (_auto_best, (_preferred_backend or "").strip().lower(), _preferred_voice)
    if _backend is not None and _backend_key == key:
        return _backend

    ctx = _prism_get_context()
    if not ctx:
        _backend = False
        _backend_key = key
        return _backend

    try:
        if _auto_best or not _preferred_backend:
            _backend = ctx.create_best()
        else:
            _backend = _prism_create_backend_for_name(ctx, _preferred_backend)
        _prism_apply_voice_preference(_backend)
        _backend_key = key
    except ValueError as e:
        log.debug("No usable Prism backend found: %s", e)
        _backend = False
        _backend_key = key
    except Exception as e:
        log.debug("Failed to initialize announcement backend: %s", e)
        _backend = False
        _backend_key = key
    return _backend


def _prism_list_backends():
    ctx = _prism_get_context()
    if not ctx:
        return []
    backends = []
    try:
        for i in range(ctx.backends_count):
            backend_id = ctx.id_of(i)
            if not ctx.exists(backend_id):
                continue
            backends.append(
                {
                    "id": backend_id.name,
                    "name": ctx.name_of(backend_id),
                }
            )
    except Exception as e:
        log.debug("Failed to enumerate announcement backends: %s", e)
    return backends


def _prism_list_voices(backend_name=""):
    ctx = _prism_get_context()
    if not ctx:
        return []
    voices = []
    try:
        backend = _prism_create_backend_for_name(ctx, backend_name)
        features = backend.features
        if getattr(features, "supports_refresh_voices", False):
            backend.refresh_voices()
        if not getattr(features, "supports_count_voices", False):
            return []
        count = backend.voices_count
        for i in range(count):
            name = f"Voice {i}"
            lang = ""
            if getattr(features, "supports_get_voice_name", False):
                try:
                    name = backend.get_voice_name(i)
                except Exception:
                    pass
            if getattr(features, "supports_get_voice_language", False):
                try:
                    lang = backend.get_voice_language(i)
                except Exception:
                    pass
            voices.append(
                {
                    "index": i,
                    "name": name,
                    "language": lang,
                }
            )
    except Exception as e:
        log.debug("Failed to enumerate announcement voices: %s", e)
    return voices


# ======================================================================
# accessible_output2 path (Windows 8.1 and earlier)
# ======================================================================

# Module-name -> attribute-name pairs for the output classes we support.
# Order matches accessible_output2.outputs.auto's natural priority sweep.
_AO2_OUTPUTS = (
    ("nvda", "NVDA"),
    ("jaws", "Jaws"),
    ("window_eyes", "WindowEyes"),
    ("dolphin", "Dolphin"),
    ("system_access", "SystemAccess"),
    ("pc_talker", "PCTalker"),
    ("sapi5", "SAPI5"),
)

_ao2_classes_cache = None


def _ao2_get_classes():
    """Return the list of accessible_output2 Output classes in priority
    order, importing them lazily."""
    global _ao2_classes_cache
    if _ao2_classes_cache is not None:
        return _ao2_classes_cache
    classes = []
    try:
        from accessible_output2.outputs import base
    except Exception as e:
        log.debug("accessible_output2 not available: %s", e)
        _ao2_classes_cache = []
        return _ao2_classes_cache
    for mod_name, cls_name in _AO2_OUTPUTS:
        try:
            mod = __import__(
                f"accessible_output2.outputs.{mod_name}",
                fromlist=[cls_name],
            )
            cls = getattr(mod, cls_name, None)
            if cls is None or not isinstance(cls, type):
                continue
            if not issubclass(cls, base.Output) or cls is base.Output:
                continue
            classes.append(cls)
        except Exception as e:
            log.debug("Failed to import ao2 backend %s: %s", mod_name, e)
    _ao2_classes_cache = classes
    return classes


def _ao2_find_class(backend_name):
    """Return the Output class whose ``name`` attribute matches
    ``backend_name`` (case-insensitive). Falls back to comparing the class
    name itself."""
    target = _normalize_backend_token(backend_name)
    if not target:
        return None
    for cls in _ao2_get_classes():
        candidates = [
            getattr(cls, "name", ""),
            getattr(cls, "__name__", ""),
        ]
        for cand in candidates:
            if _normalize_backend_token(cand) == target:
                return cls
    return None


def _ao2_apply_voice_preference(instance):
    if _preferred_voice < 0:
        return
    try:
        if not hasattr(instance, "list_voices") or not hasattr(instance, "set_voice"):
            return
        voices = instance.list_voices()
        if 0 <= _preferred_voice < len(voices):
            instance.set_voice(voices[_preferred_voice])
    except Exception as e:
        log.debug("Failed to apply ao2 voice preference: %s", e)


def _ao2_get_backend():
    global _backend, _backend_key
    key = (_auto_best, (_preferred_backend or "").strip().lower(), _preferred_voice)
    if _backend is not None and _backend_key == key:
        return _backend

    instance = None
    if _auto_best or not _preferred_backend:
        try:
            from accessible_output2.outputs.auto import Auto

            instance = Auto()
        except Exception as e:
            log.debug("Failed to init accessible_output2 Auto: %s", e)
    else:
        cls = _ao2_find_class(_preferred_backend)
        if cls is None:
            log.debug(
                "Requested ao2 backend %r not found; falling back to Auto",
                _preferred_backend,
            )
            try:
                from accessible_output2.outputs.auto import Auto

                instance = Auto()
            except Exception as e:
                log.debug("Failed to init accessible_output2 Auto: %s", e)
        else:
            try:
                instance = cls()
            except Exception as e:
                log.debug("Failed to init ao2 backend %s: %s", cls.__name__, e)

    if instance is not None:
        # Auto() exposes the chosen backend on .output; voice prefs apply to
        # that underlying class instance.
        target = getattr(instance, "output", instance)
        _ao2_apply_voice_preference(target)

    _backend = instance if instance is not None else False
    _backend_key = key
    return _backend


def _ao2_list_backends():
    """Return ``[{'id': name, 'name': display}]`` for every accessible_output2
    output that can be successfully constructed on this machine."""
    backends = []
    for cls in _ao2_get_classes():
        try:
            cls()  # availability check
        except Exception:
            continue
        backend_id = getattr(cls, "name", cls.__name__)
        backends.append({"id": backend_id, "name": cls.__name__})
    return backends


def _ao2_list_voices(backend_name=""):
    """List voices for the named backend. accessible_output2 only exposes
    voice lists for SAPI5; other screen readers manage their own voice
    selection internally, so they return an empty list."""
    cls = None
    if backend_name:
        cls = _ao2_find_class(backend_name)
    else:
        try:
            from accessible_output2.outputs.auto import Auto

            inst = Auto()
            target = getattr(inst, "output", inst)
            cls = type(target)
        except Exception as e:
            log.debug("Failed to resolve ao2 default backend: %s", e)
    if cls is None:
        return []
    try:
        instance = cls()
    except Exception:
        return []
    if not hasattr(instance, "list_voices"):
        return []
    try:
        names = instance.list_voices()
    except Exception:
        return []
    return [
        {"index": i, "name": name, "language": ""}
        for i, name in enumerate(names)
    ]

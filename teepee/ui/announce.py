import logging

log = logging.getLogger(__name__)

_ctx = None
_backend = None
_enabled = False
_auto_best = True
_preferred_backend = ""
_preferred_voice = -1
_backend_key = None


def _normalize_backend_token(value):
    return "".join(ch for ch in str(value).upper() if ch.isalnum())


def _get_context():
    global _ctx
    if _ctx is not None:
        return _ctx
    try:
        from prism import Context

        _ctx = Context()
    except ImportError:
        log.debug("Prism not available; screen reader announcements disabled")
        _ctx = False
    except Exception as e:
        log.debug("Failed to initialize Prism context: %s", e)
        _ctx = False
    return _ctx


def _create_backend_for_name(ctx, backend_name):
    if not backend_name:
        return ctx.create_best()
    backend_id = _resolve_backend_id(ctx, backend_name)
    return ctx.create(backend_id)


def _resolve_backend_id(ctx, backend_name):
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


def _apply_voice_preference(backend):
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


def _get_backend():
    global _backend, _backend_key
    key = (_auto_best, (_preferred_backend or "").strip().lower(), _preferred_voice)
    if _backend is not None and _backend_key == key:
        return _backend

    ctx = _get_context()
    if not ctx:
        _backend = False
        _backend_key = key
        return _backend

    try:
        if _auto_best or not _preferred_backend:
            _backend = ctx.create_best()
        else:
            _backend = _create_backend_for_name(ctx, _preferred_backend)
        _apply_voice_preference(_backend)
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


def announce(text, interrupt=False):
    """Announce text through Prism's best available backend."""
    if not _enabled:
        return
    if not text:
        return
    backend = _get_backend()
    if not backend:
        return
    try:
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
    ctx = _get_context()
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


def list_announcement_voices(backend_name=""):
    ctx = _get_context()
    if not ctx:
        return []
    voices = []
    try:
        backend = _create_backend_for_name(ctx, backend_name)
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

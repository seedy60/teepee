"""Encrypted application credential store.

API credentials are XOR-encrypted with a key derived via PBKDF2
from multiple application constants.  Run ``setup_credentials.py``
once to encrypt your Telegram API ID and hash, then paste the
output into ``_API_ID_ENC`` and ``_API_HASH_ENC`` below.
"""
from __future__ import annotations

import hashlib


# Application build metadata used in key derivation.
# Changing any of these invalidates existing encrypted credentials.
_BUILD_EPOCH = "20260407"
_WIDGET_TOOLKIT = "wx-phoenix-4"
_PROTOCOL_TAG = "mtproto-layer-166"
_RENDER_ENGINE = "native-win-cocoa"
_SESSION_SCHEMA = "telethon-v1-sqlite"

# Encrypted credential blobs (hex-encoded).
# Populate by running:  python setup_credentials.py
_API_ID_ENC = "316f91c86573f6c2"                                                                                        
_API_HASH_ENC = "656dc6c3367df6c068f8295563bb3938d1accb7ec4a6606faaac01642fd181a4"

def _derive_key(length: int) -> bytes:
    parts = [
        _BUILD_EPOCH.encode(),
        _WIDGET_TOOLKIT.encode(),
        _PROTOCOL_TAG.encode(),
        _RENDER_ENGINE.encode(),
        _SESSION_SCHEMA.encode(),
    ]
    combined = b"\x1f".join(parts)
    pre_salt = hashlib.sha384(combined).digest()
    salt = pre_salt[:16]
    stretched = hashlib.pbkdf2_hmac(
        "sha256", combined, salt, iterations=180_000
    )
    return stretched[:length]


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(d ^ key[i % len(key)] for i, d in enumerate(data))


def get_credentials() -> tuple[str, str] | None:
    """Return ``(api_id, api_hash)`` or ``None`` if not configured."""
    if not _API_ID_ENC or not _API_HASH_ENC:
        return None
    try:
        enc_id = bytes.fromhex(_API_ID_ENC)
        enc_hash = bytes.fromhex(_API_HASH_ENC)
        key = _derive_key(max(len(enc_id), len(enc_hash)))
        api_id = _xor_bytes(enc_id, key).decode("utf-8")
        api_hash = _xor_bytes(enc_hash, key).decode("utf-8")
        return api_id, api_hash
    except Exception:
        return None

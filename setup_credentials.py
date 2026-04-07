"""One-time helper to encrypt Telegram API credentials for distribution.

Run this script, enter your API ID and hash, then paste the printed
constants into ``teepee/credentials.py``.
"""
import getpass
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from teepee.credentials import _derive_key, _xor_bytes


def main():
    print("Teepee credential encryptor")
    print("=" * 40)
    print()
    api_id = input("API ID:   ").strip()
    api_hash = input("API Hash: ").strip()

    if not api_id or not api_hash:
        print("Both values are required.")
        sys.exit(1)

    key_len = max(len(api_id), len(api_hash))
    key = _derive_key(key_len)

    enc_id = _xor_bytes(api_id.encode("utf-8"), key).hex()
    enc_hash = _xor_bytes(api_hash.encode("utf-8"), key).hex()

    # Verify round-trip
    dec_id = _xor_bytes(bytes.fromhex(enc_id), key).decode("utf-8")
    dec_hash = _xor_bytes(bytes.fromhex(enc_hash), key).decode("utf-8")
    assert dec_id == api_id, "Round-trip check failed for API ID"
    assert dec_hash == api_hash, "Round-trip check failed for API Hash"

    print()
    print("Paste the following into teepee/credentials.py:")
    print("-" * 50)
    print(f'_API_ID_ENC = "{enc_id}"')
    print(f'_API_HASH_ENC = "{enc_hash}"')
    print("-" * 50)
    print()
    print("Round-trip verified successfully.")


if __name__ == "__main__":
    main()

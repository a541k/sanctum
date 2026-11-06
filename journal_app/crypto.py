"""Encryption primitives: AES-256-GCM for data, scrypt for password -> key.

Everything here is language-neutral and standard, so a future web/mobile
version can read the same vault.
"""
import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

KEY_LEN = 32
NONCE_LEN = 12


class DecryptionError(Exception):
    """Wrong key or corrupted/tampered data."""


def new_key() -> bytes:
    return os.urandom(KEY_LEN)


def derive_key(password: str, salt: bytes, n: int = 2**15, r: int = 8, p: int = 1) -> bytes:
    return Scrypt(salt=salt, length=KEY_LEN, n=n, r=r, p=p).derive(password.encode("utf-8"))


def encrypt(key: bytes, data: bytes, aad: bytes = b"") -> bytes:
    """Returns nonce (12 bytes) + ciphertext + 16-byte auth tag."""
    nonce = os.urandom(NONCE_LEN)
    return nonce + AESGCM(key).encrypt(nonce, data, aad)


def decrypt(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    try:
        return AESGCM(key).decrypt(blob[:NONCE_LEN], blob[NONCE_LEN:], aad)
    except (InvalidTag, ValueError):
        raise DecryptionError("Decryption failed")


# ---- recovery key helpers -------------------------------------------------

def generate_recovery_key() -> tuple[bytes, str]:
    """Returns (raw 32-byte key, human-friendly string like ABCD-EFGH-...)."""
    raw = os.urandom(KEY_LEN)
    text = base64.b32encode(raw).decode().rstrip("=")
    return raw, "-".join(text[i:i + 4] for i in range(0, len(text), 4))


def parse_recovery_key(text: str) -> bytes:
    cleaned = "".join(text.split()).replace("-", "").upper()
    cleaned += "=" * (-len(cleaned) % 8)
    try:
        raw = base64.b32decode(cleaned)
    except Exception:
        raise DecryptionError("Malformed recovery key")
    if len(raw) != KEY_LEN:
        raise DecryptionError("Malformed recovery key")
    return raw

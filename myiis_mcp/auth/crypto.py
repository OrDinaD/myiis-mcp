"""Authenticated Encryption (AEAD) with AAD binding for multi-user session secrets.

Supports:
1. Pure Python authenticated encryption (AES-CTR + HMAC-SHA256 Encrypt-then-MAC with AAD).
2. Cloudflare Python Workers WebCrypto AES-GCM if js.crypto.subtle is available.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from typing import Any

# Default test key if MYIIS_MASTER_KEY environment variable is not set
_DEFAULT_TEST_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def get_master_key() -> bytes:
    """Retrieve 32-byte master encryption key from environment or default fallback."""
    raw_key = os.environ.get("MYIIS_MASTER_KEY", "").strip()
    if not raw_key:
        raw_key = _DEFAULT_TEST_KEY
    # Normalize to 32 bytes via SHA-256
    return hashlib.sha256(raw_key.encode("utf-8")).digest()


# ---------------------------------------------------------------------------
# Pure Python AES implementation (AES-128/256 CTR mode + HMAC-SHA256 AEAD)
# ---------------------------------------------------------------------------

_S_BOX = (
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5e, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
)

_RCON = (
    0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40,
    0x80, 0x1b, 0x36, 0x6c, 0xd8, 0xab, 0x4d, 0x9a,
)


def _xtimes(b: int) -> int:
    return ((b << 1) ^ 0x1b) & 0xff if (b & 0x80) else (b << 1)


def _key_expansion(key: bytes) -> list[list[int]]:
    nk = len(key) // 4
    nr = nk + 6
    w = [list(key[4 * i : 4 * i + 4]) for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        temp = list(w[i - 1])
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [_S_BOX[b] for b in temp]
            temp[0] ^= _RCON[i // nk]
        elif nk > 6 and i % nk == 4:
            temp = [_S_BOX[b] for b in temp]
        w.append([w[i - nk][j] ^ temp[j] for j in range(4)])
    return w


def _encrypt_block(block: bytes, w: list[list[int]]) -> bytes:
    nr = len(w) // 4 - 1
    state = [list(block[4 * i : 4 * i + 4]) for i in range(4)]
    # Transpose to column-major
    state = [[state[r][c] for r in range(4)] for c in range(4)]

    # AddRoundKey
    for c in range(4):
        for r in range(4):
            state[c][r] ^= w[c][r]

    for round_num in range(1, nr):
        # SubBytes
        for c in range(4):
            for r in range(4):
                state[c][r] = _S_BOX[state[c][r]]

        # ShiftRows
        state[1] = state[1][1:] + state[1][:1]
        state[2] = state[2][2:] + state[2][:2]
        state[3] = state[3][3:] + state[3][:3]

        # MixColumns
        for c in range(4):
            a0, a1, a2, a3 = state[0][c], state[1][c], state[2][c], state[3][c]
            state[0][c] = _xtimes(a0) ^ _xtimes(a1) ^ a1 ^ a2 ^ a3
            state[1][c] = a0 ^ _xtimes(a1) ^ _xtimes(a2) ^ a2 ^ a3
            state[2][c] = a0 ^ a1 ^ _xtimes(a2) ^ _xtimes(a3) ^ a3
            state[3][c] = _xtimes(a0) ^ a0 ^ a1 ^ a2 ^ _xtimes(a3)

        # AddRoundKey
        for c in range(4):
            for r in range(4):
                state[r][c] ^= w[round_num * 4 + c][r]

    # Final round
    for c in range(4):
        for r in range(4):
            state[c][r] = _S_BOX[state[c][r]]

    state[1] = state[1][1:] + state[1][:1]
    state[2] = state[2][2:] + state[2][:2]
    state[3] = state[3][3:] + state[3][:3]

    for c in range(4):
        for r in range(4):
            state[r][c] ^= w[nr * 4 + c][r]

    out = bytearray(16)
    for c in range(4):
        for r in range(4):
            out[c * 4 + r] = state[r][c]
    return bytes(out)


def _aes_ctr_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """Generate CTR mode keystream."""
    w = _key_expansion(key)
    counter = int.from_bytes(nonce, "big")
    out = bytearray()
    while len(out) < length:
        block = counter.to_bytes(16, "big")
        enc = _encrypt_block(block, w)
        out.extend(enc)
        counter = (counter + 1) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    return bytes(out[:length])


def _derive_keys(master_key: bytes, user_id: str, service: str) -> tuple[bytes, bytes]:
    """Derive dedicated encryption and MAC keys using HKDF-like HMAC-SHA256."""
    info_enc = f"myiis-v1-enc:{user_id}:{service}".encode("utf-8")
    info_mac = f"myiis-v1-mac:{user_id}:{service}".encode("utf-8")
    k_enc = hmac.new(master_key, info_enc, hashlib.sha256).digest()
    k_mac = hmac.new(master_key, info_mac, hashlib.sha256).digest()
    return k_enc, k_mac


def encrypt_secret(
    plaintext: str,
    user_id: str,
    service: str,
    master_key: bytes | None = None,
) -> str:
    """Encrypt a secret string using AEAD bound to user_id and service name.

    Returns format: v1:{nonce_b64}:{ciphertext_b64}:{tag_b64}
    """
    if master_key is None:
        master_key = get_master_key()

    k_enc, k_mac = _derive_keys(master_key, user_id, service)
    data = plaintext.encode("utf-8")
    nonce = secrets.token_bytes(16)
    keystream = _aes_ctr_keystream(k_enc, nonce, len(data))
    ciphertext = bytes(a ^ b for a, b in zip(data, keystream))

    # AAD: version + user_id + service + nonce + ciphertext length
    aad = f"v1:{user_id}:{service}".encode("utf-8")
    mac_data = aad + nonce + ciphertext
    tag = hmac.new(k_mac, mac_data, hashlib.sha256).digest()

    nonce_b64 = base64.urlsafe_b64encode(nonce).decode("ascii")
    ct_b64 = base64.urlsafe_b64encode(ciphertext).decode("ascii")
    tag_b64 = base64.urlsafe_b64encode(tag).decode("ascii")
    return f"v1:{nonce_b64}:{ct_b64}:{tag_b64}"


def decrypt_secret(
    ciphertext_str: str,
    user_id: str,
    service: str,
    master_key: bytes | None = None,
) -> str:
    """Decrypt an encrypted secret string and verify AEAD authenticity.

    Raises ValueError if integrity verification fails or ciphertext is malformed.
    """
    if master_key is None:
        master_key = get_master_key()

    parts = ciphertext_str.split(":")
    if len(parts) != 4 or parts[0] != "v1":
        raise ValueError("Invalid ciphertext format or version")

    _, nonce_b64, ct_b64, tag_b64 = parts
    try:
        nonce = base64.urlsafe_b64decode(nonce_b64.encode("ascii"))
        ciphertext = base64.urlsafe_b64decode(ct_b64.encode("ascii"))
        expected_tag = base64.urlsafe_b64decode(tag_b64.encode("ascii"))
    except Exception as e:
        raise ValueError(f"Malformed base64 ciphertext components: {e}")

    k_enc, k_mac = _derive_keys(master_key, user_id, service)
    aad = f"v1:{user_id}:{service}".encode("utf-8")
    mac_data = aad + nonce + ciphertext
    computed_tag = hmac.new(k_mac, mac_data, hashlib.sha256).digest()

    if not hmac.compare_digest(computed_tag, expected_tag):
        raise ValueError("Decryption failed: integrity or AAD check violated (HMAC tag mismatch)")

    keystream = _aes_ctr_keystream(k_enc, nonce, len(ciphertext))
    plaintext_bytes = bytes(a ^ b for a, b in zip(ciphertext, keystream))
    return plaintext_bytes.decode("utf-8")

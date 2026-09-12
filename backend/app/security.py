"""Cryptographic primitives for CryptoTrace.

Everything here uses only the Python standard library so the backend keeps
running in fully-offline environments (tests, demos) with zero extra
dependencies:

- Password hashing: PBKDF2-HMAC-SHA256 with a per-user salt. The stored format
  is ``pbkdf2$<iterations>$<salt_hex>$<hash_hex>``.
- Token signing: HMAC-SHA256 over ``header.payload`` (base64url). The format is
  JWT-like but self-contained so we do not need a JWT library.

SECURITY RULES
--------------
- Never log a password, a token, or a derived secret. Callers that need to log
  events (audit trail) pass only identifiers and result codes.
- Verifications must use ``secrets.compare_digest`` (constant time).
- The auth secret comes from settings. In development a random secret is
  generated once and persisted to a git-ignored dotfile so tokens survive
  restart; it is never logged or shipped.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

_PBKDF2_ITERATIONS = 210_000
_HASH_ALG = "sha256"
_SALT_BYTES = 16

# Token shape: "v1.<header_b64>.<payload_b64>.<sig_b64>"
_TOKEN_ALG = "HS256"
_TOKEN_VERSION = "v1"
_TOKEN_TTL_SECONDS = 2 * 60 * 60  # overridden by settings at token creation


class PasswordPolicyError(ValueError):
    """Raised when a proposed password does not satisfy the policy."""


class TokenError(ValueError):
    """Raised when a token cannot be parsed, is malformed, or is invalid."""


def hash_password(password: str, salt: Optional[bytes] = None, iterations: int = _PBKDF2_ITERATIONS) -> str:
    """Return a salted PBKDF2-HMAC-SHA256 hash string for ``password``.

    The password is stored in the form ``pbkdf2$<iter>$<salt_hex>$<hash_hex>``.
    Neither the password nor the salt are recoverable from the hash.
    """
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    pw = password.encode("utf-8")
    salt = salt or secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(_HASH_ALG, pw, salt, iterations)
    return f"pbkdf2${iterations}${salt.hex()}${digest.hex()}"


def verify_password(stored: str, candidate: str) -> bool:
    """Constant-time verification of ``candidate`` against a stored hash."""
    try:
        scheme, iterations_s, salt_hex, hash_hex = stored.split("$")
        if scheme != "pbkdf2":
            return False
        iterations = int(iterations_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac(_HASH_ALG, candidate.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


_WHITESPACE = re.compile(r"\s")
_PURE_DIGITS = re.compile(r"^\d+$")


def validate_password_policy(password: str, username: str = "") -> Optional[str]:
    """Validate a password against the CryptoTrace policy.

    Returns ``None`` when acceptable, otherwise a human-safe reason.
    """
    if not isinstance(password, str) or not password:
        return "Password length must be at least 12 characters."
    if len(password) < 12:
        return "Password length must be at least 12 characters."
    if len(password) > 200:
        return "Password length must be at most 200 characters."
    if _WHITESPACE.search(password):
        return "Password must not contain whitespace."
    if _PURE_DIGITS.match(password):
        return "Password must not be entirely numeric."
    if username and username.lower() in password.lower():
        return "Password must not contain the username."
    return None


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_signed_token(
    payload: Dict[str, Any],
    secret: str,
    ttl_seconds: int = _TOKEN_TTL_SECONDS,
) -> str:
    """Create an HMAC-SHA256 signed token carrying ``payload`` plus ``exp``."""
    if not secret:
        raise TokenError("A token signing secret is not configured.")
    body = dict(payload)
    body["exp"] = int(time.time()) + ttl_seconds
    header = {"alg": _TOKEN_ALG, "typ": "JWT"}
    header_b64 = _b64url_encode(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    payload_b64 = _b64url_encode(
        json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{_TOKEN_VERSION}.{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{signing_input.decode('ascii')}.{_b64url_encode(sig)}"


def decode_signed_token(token: str, secret: str) -> Dict[str, Any]:
    """Decode and verify a signed token; return its payload.

    Raises :class:`TokenError` for malformed, tampered, or expired tokens.
    """
    if not token or not secret:
        raise TokenError("Token verification is not configured.")
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != _TOKEN_VERSION:
        raise TokenError("Malformed token.")
    version, header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{version}.{header_b64}.{payload_b64}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        supplied = _b64url_decode(sig_b64)
    except (ValueError, UnicodeDecodeError) as exc:
        raise TokenError("Malformed token.") from exc
    if not hmac.compare_digest(expected, supplied):
        raise TokenError("Token signature is invalid.")

    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise TokenError("Malformed token.") from exc

    if header.get("alg") != _TOKEN_ALG:
        raise TokenError("Unsupported token algorithm.")
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise TokenError("Token has expired.")
    return payload


def new_token_secret() -> str:
    """Generate a fresh random token-signing secret (development default)."""
    return secrets.token_hex(32)


@dataclass(frozen=True)
class SessionIdentity:
    """Decoded identity carried by an access token."""

    user_id: str
    username: str
    role: str
    token_type: str = "access"

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "SessionIdentity":
        try:
            return cls(
                user_id=str(payload["sub"]),
                username=str(payload["username"]),
                role=str(payload["role"]),
                token_type=str(payload.get("type", "access")),
            )
        except KeyError as exc:
            raise TokenError("Token payload is missing identity claims.") from exc


def secure_compare(provided: str, expected: str) -> bool:
    """Constant-time string comparison helper."""
    compare_arr = bytearray(expected.encode("utf-8"))
    return hmac.compare_digest(compare_arr, bytearray(provided.encode("utf-8")))


def _to_pair(stored: str) -> Tuple[str, str]:
    scheme, iterations, salt_hex, hash_hex = stored.split("$")
    return scheme, f"{iterations}${salt_hex}${hash_hex}"
"""Security primitives tests: password hashing, token signing, policy, compare."""

from __future__ import annotations

import base64
import json
import time

import pytest

from app.security import (
    PasswordPolicyError,
    TokenError,
    create_signed_token,
    decode_signed_token,
    hash_password,
    secure_compare,
    validate_password_policy,
    verify_password,
)

SECRET = "unit-test-secret-key-0001"


class TestPasswordHashing:
    def test_hash_and_verify_roundtrip(self):
        stored = hash_password("S3cure-Password-123")
        assert verify_password(stored, "S3cure-Password-123") is True
        assert verify_password(stored, "wrong") is False

    def test_salt_makes_hashes_unique(self):
        assert hash_password("same-password-001") != hash_password("same-password-001")

    def test_hash_format(self):
        stored = hash_password("a-strong-pass-000", salt=b"fixed-salt-16bytes")
        scheme, iterations, salt_hex, _hash = stored.split("$")
        assert scheme == "pbkdf2"
        assert int(iterations) == 210_000
        assert salt_hex == "fixed-salt-16bytes".encode().hex()

    def test_malformed_stored_hash_returns_false(self):
        assert verify_password("not-a-pbkdf2-hash", "anything") is False
        assert verify_password("pbkdf2$abc$zz", "anything") is False

    def test_type_error_for_non_string(self):
        with pytest.raises(TypeError):
            hash_password(12345)  # type: ignore[arg-type]


class TestTokenSigning:
    def test_roundtrip_payload(self):
        token = create_signed_token(
            {"sub": "7", "username": "investigator", "role": "investigator", "type": "access"},
            secret=SECRET,
            ttl_seconds=3600,
        )
        payload = decode_signed_token(token, SECRET)
        assert payload["sub"] == "7"
        assert payload["username"] == "investigator"
        assert payload["role"] == "investigator"

    def test_expires_set(self):
        token = create_signed_token({"sub": "1"}, secret=SECRET, ttl_seconds=60)
        payload = decode_signed_token(token, SECRET)
        assert payload["exp"] > int(time.time())

    def test_tampered_token_rejected(self):
        token = create_signed_token({"sub": "1", "role": "read_only"}, secret=SECRET)
        tampered = token[:-2] + ("ab" if not token.endswith("ab") else "cd")
        with pytest.raises(TokenError):
            decode_signed_token(tampered, SECRET)

    def test_wrong_secret_rejected(self):
        token = create_signed_token({"sub": "1"}, secret=SECRET)
        with pytest.raises(TokenError):
            decode_signed_token(token, "different-secret-key-999")

    def test_malformed_token_rejected(self):
        for bad in ("", "abc", "v1..", "v1.a.b.c.d"):
            with pytest.raises(TokenError):
                decode_signed_token(bad, SECRET)

    def test_expired_token_rejected(self):
        token = create_signed_token({"sub": "1"}, secret=SECRET, ttl_seconds=-10)
        with pytest.raises(TokenError):
            decode_signed_token(token, SECRET)

    def test_missing_secret_raises(self):
        with pytest.raises(TokenError):
            create_signed_token({"sub": "1"}, secret="")

    def test_payload_json_is_compact(self):
        token = create_signed_token({"sub": "1"}, secret=SECRET)
        # token = v1.<header>.<payload>.<sig>
        header_b64 = token.split(".")[1]
        header_raw = base64.urlsafe_b64decode(header_b64 + "==")
        header = json.loads(header_raw)
        assert header["alg"] == "HS256"


class TestPasswordPolicy:
    def test_too_short(self):
        assert validate_password_policy("abc") is not None
        assert "12 characters" in validate_password_policy("abc")

    def test_too_long(self):
        assert validate_password_policy("x" * 201) is not None

    def test_whitespace_rejected(self):
        assert validate_password_policy("pass word-12345") is not None

    def test_all_numeric_rejected(self):
        assert validate_password_policy("123456789012", username="admin") is not None

    def test_username_inside_password_rejected(self):
        assert validate_password_policy("admin-super-secret", username="admin") is not None

    def test_valid_password_returns_none(self):
        assert validate_password_policy("H4rd-To-Guess-Pass!2026", username="admin") is None


class TestSecureCompare:
    def test_compare_equal(self):
        assert secure_compare("expected", "expected") is True

    def test_compare_different(self):
        assert secure_compare("expected", "other") is False
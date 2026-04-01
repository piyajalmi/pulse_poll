import pytest

from utils import security


def test_hash_ip_is_deterministic_and_sha256_length():
    first = security.hash_ip("127.0.0.1")
    second = security.hash_ip("127.0.0.1")

    assert first == second
    assert len(first) == 64
    assert first != security.hash_ip("192.168.0.10")


def test_encrypt_decrypt_roundtrip(monkeypatch):
    monkeypatch.setattr(security.Config, "ENCRYPTION_KEY", "roundtrip_test_key_123")
    original = "userhash_42"
    encrypted = security.encrypt_identifier(original)

    assert isinstance(encrypted, str)
    assert encrypted != original
    assert security.decrypt_identifier(encrypted) == original


def test_get_encryption_key_returns_exactly_32_bytes(monkeypatch):
    monkeypatch.setattr(security.Config, "ENCRYPTION_KEY", "short_key")

    key = security.get_encryption_key()

    assert isinstance(key, bytes)
    assert len(key) == 32


def test_get_encryption_key_raises_when_missing(monkeypatch):
    monkeypatch.setattr(security.Config, "ENCRYPTION_KEY", None)

    with pytest.raises(ValueError, match="Encryption key not set"):
        security.get_encryption_key()

"""The presign HMAC key must not keep a publicly known production default."""

from __future__ import annotations

from novara_core.modules import storage

LEGACY_DEV_SECRET = b"novara-dev-presign-secret"


def test_explicit_secret_is_used_verbatim(monkeypatch):
    monkeypatch.setenv("NOVARA_PRESIGN_SECRET", "owner-provided-key")
    monkeypatch.delenv("NOVARA_DEV_MODE", raising=False)
    assert storage._default_presign_secret() == b"owner-provided-key"


def test_dev_mode_preserves_legacy_convenience(monkeypatch):
    monkeypatch.delenv("NOVARA_PRESIGN_SECRET", raising=False)
    monkeypatch.setenv("NOVARA_DEV_MODE", "true")
    assert storage._default_presign_secret() == LEGACY_DEV_SECRET


def test_non_dev_default_is_unpredictable(monkeypatch):
    monkeypatch.delenv("NOVARA_PRESIGN_SECRET", raising=False)
    monkeypatch.delenv("NOVARA_DEV_MODE", raising=False)
    first = storage._default_presign_secret()
    second = storage._default_presign_secret()
    assert first != LEGACY_DEV_SECRET
    assert len(first) >= 32
    assert first != second

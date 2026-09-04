import pytest

from app.config import Settings
from app.core.security import DEV_SECRET_KEY, resolve_secret_key


def test_dev_secret_fallback_only_in_debug(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    secret = resolve_secret_key(Settings(DEBUG=True, SECRET_KEY=None))

    assert secret == DEV_SECRET_KEY


def test_secret_required_when_debug_false(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY or JWT_SECRET_KEY"):
        resolve_secret_key(Settings(DEBUG=False, SECRET_KEY=None))

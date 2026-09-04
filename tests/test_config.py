from app.config import Settings


def test_debug_accepts_release_as_false():
    settings = Settings(DEBUG="release")

    assert settings.DEBUG is False


def test_debug_accepts_development_as_true():
    settings = Settings(DEBUG="development")

    assert settings.DEBUG is True

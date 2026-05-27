from backend.observability import sentry


def test_sentry_is_disabled_without_dsn(monkeypatch):

    monkeypatch.setattr(
        sentry.settings,
        "SENTRY_DSN",
        ""
    )

    assert sentry.init_sentry() is False

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from backend.config import settings


def init_sentry():

    if not settings.SENTRY_DSN:

        return False

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        release=settings.APP_RELEASE,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[
            FastApiIntegration()
        ],
        send_default_pii=False
    )

    return True

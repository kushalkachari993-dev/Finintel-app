import logging

from backend.config.settings import (
    LOG_LEVEL
)


def configure_logging():

    logging.basicConfig(
        level=getattr(
            logging,
            LOG_LEVEL.upper(),
            logging.INFO
        ),
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s %(message)s"
        )
    )

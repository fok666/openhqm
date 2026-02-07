"""HTTP API listener entrypoint."""

import uvicorn
import structlog

from openhqm.api.app import create_app
from openhqm.config import settings
from openhqm.utils.logging import setup_logging

logger = structlog.get_logger(__name__)


def main():
    """Run the HTTP API listener."""
    setup_logging()
    logger.info(
        "Starting HTTP listener",
        host=settings.server.host,
        port=settings.server.port,
    )

    app = create_app()

    uvicorn.run(
        app,
        host=settings.server.host,
        port=settings.server.port,
        workers=settings.server.workers,
        log_config=None,  # Use our logging configuration
    )


if __name__ == "__main__":
    main()

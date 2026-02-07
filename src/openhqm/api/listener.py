"""HTTP API listener entrypoint."""

import structlog
import uvicorn

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

    # Use import string for uvicorn when workers > 1 (required by uvicorn)
    # Use app object when workers = 1 (development mode)
    if settings.server.workers > 1:
        # Import string required for multi-worker mode
        uvicorn.run(
            "openhqm.api.app:create_app",
            factory=True,
            host=settings.server.host,
            port=settings.server.port,
            workers=settings.server.workers,
            log_config=None,  # Use our logging configuration
        )
    else:
        # Direct app object for single-worker mode (development)
        app = create_app()
        uvicorn.run(
            app,
            host=settings.server.host,
            port=settings.server.port,
            log_config=None,  # Use our logging configuration
        )


if __name__ == "__main__":
    main()

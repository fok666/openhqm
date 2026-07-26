"""Single entrypoint for both sidecar modes.

python -m openhqm http-to-queue   # accept HTTP, enqueue, serve poll results
python -m openhqm queue-to-http   # consume queue, forward to the backend
"""

import sys

USAGE = "usage: python -m openhqm [http-to-queue|queue-to-http]"


def _run_api() -> None:
    import uvicorn

    from openhqm.config import settings
    from openhqm.logging import setup_logging

    setup_logging()
    if settings.server.workers > 1:
        # uvicorn requires an import string for multi-worker mode
        uvicorn.run(
            "openhqm.api.app:create_app",
            factory=True,
            host=settings.server.host,
            port=settings.server.port,
            workers=settings.server.workers,
            log_config=None,
        )
    else:
        from openhqm.api.app import create_app

        uvicorn.run(
            create_app(), host=settings.server.host, port=settings.server.port, log_config=None
        )


def main() -> None:
    """Run the selected sidecar mode based on command line arguments."""
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    # Drop the mode arg so downstream sys.argv parsing (e.g. worker id) is unaffected.
    sys.argv = [sys.argv[0], *sys.argv[2:]]

    if mode in ("http-to-queue", "http2queue", "api"):
        _run_api()
    elif mode in ("queue-to-http", "queue2http", "worker"):
        import asyncio

        from openhqm.worker.worker import main as run_worker

        asyncio.run(run_worker())
    else:
        sys.exit(USAGE)


if __name__ == "__main__":
    main()

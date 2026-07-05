"""Single entrypoint for both sidecar modes.

python -m openhqm http-to-queue   # accept HTTP, enqueue, serve poll results
python -m openhqm queue-to-http    # consume queue, forward to the backend
"""

import sys

USAGE = "usage: python -m openhqm [http-to-queue|queue-to-http]"


def main() -> None:
    """Run the selected sidecar mode based on command line arguments."""
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    # Drop the mode arg so downstream sys.argv parsing (e.g. worker id) is unaffected.
    sys.argv = [sys.argv[0], *sys.argv[2:]]

    if mode in ("http-to-queue", "http2queue", "api"):
        from openhqm.api.listener import main as run

        run()
    elif mode in ("queue-to-http", "queue2http", "worker"):
        import asyncio

        from openhqm.worker.worker import main as run

        asyncio.run(run())
    else:
        sys.exit(USAGE)


if __name__ == "__main__":
    main()

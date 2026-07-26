"""Minimal custom queue used by the create_queue(type=custom) test."""


class FakeQueue:
    def __init__(self, marker: int = 0):
        self.marker = marker
        self.connected = False
        self.published: list[tuple[str, dict]] = []

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.connected = False

    async def publish(self, queue_name, message) -> None:
        self.published.append((queue_name, message))

    async def consume(self, queue_name, handler, batch_size=10) -> None:
        for _, message in self.published:
            await handler(message)
